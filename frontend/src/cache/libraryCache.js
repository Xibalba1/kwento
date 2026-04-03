import { logImageEvent } from "../debug/imageDebug";

const METADATA_CACHE_VERSION = 1;
const FULL_BOOK_SCHEMA_VERSION = 2;
const SHELF_COVER_SCHEMA_VERSION = 1;
const METADATA_TTL_MS = 7 * 24 * 60 * 60 * 1000;
const FULL_BOOK_TTL_MS = 3 * 24 * 60 * 60 * 1000;
const SHELF_COVER_TTL_MS = 2 * 24 * 60 * 60 * 1000;
const SIGNED_URL_EXPIRY_BUFFER_MS = 5 * 60 * 1000;
const FULL_BOOK_MAX_BYTES = 100 * 1024 * 1024;
const SHELF_COVER_MAX_BYTES = 25 * 1024 * 1024;
const DB_NAME = "kwento-cache";
const DB_VERSION = 2;
const ASSETS_STORE = "assets";
const BOOKS_STORE = "books";
const METADATA_KEY = "kwento_shelf_metadata_v1";
const CACHE_CLASS_FULL_BOOK = "full-book";
const CACHE_CLASS_SHELF_COVER = "shelf-cover";

let dbPromise = null;
let maintenancePromise = null;
let maintenanceComplete = false;

const hasLocalStorage = () => typeof window !== "undefined" && window.localStorage;
const hasIndexedDb = () => typeof window !== "undefined" && window.indexedDB;

const now = () => Date.now();

const withExpiry = (value = {}, ttlMs) => {
  const updatedAt = value.updatedAt ?? now();
  return {
    ...value,
    updatedAt,
    expiresAt: value.expiresAt ?? updatedAt + ttlMs,
  };
};

const readLocalStorageJson = (key) => {
  if (!hasLocalStorage()) {
    return null;
  }

  try {
    const raw = window.localStorage.getItem(key);
    return raw ? JSON.parse(raw) : null;
  } catch (error) {
    console.warn(`Failed to parse cache entry for ${key}:`, error);
    return null;
  }
};

const writeLocalStorageJson = (key, value) => {
  if (!hasLocalStorage()) {
    return;
  }

  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch (error) {
    console.warn(`Failed to persist cache entry for ${key}:`, error);
  }
};

const resetDatabasePromise = () => {
  dbPromise = null;
  maintenancePromise = null;
  maintenanceComplete = false;
};

const isRecoverableDatabaseError = (error) => {
  if (!error) {
    return false;
  }

  const errorName = error.name ?? "";
  const errorMessage = error.message ?? "";

  return (
    errorName === "InvalidStateError" ||
    errorName === "AbortError" ||
    errorMessage.includes("connection is closing") ||
    errorMessage.includes("database connection is closing")
  );
};

const attachDatabaseLifecycleHandlers = (db) => {
  if (!db) {
    return;
  }

  db.onversionchange = () => {
    resetDatabasePromise();
    db.close();
  };

  if ("onclose" in db) {
    db.onclose = () => {
      resetDatabasePromise();
    };
  }
};

const openDatabase = () => {
  if (!hasIndexedDb()) {
    logImageEvent("cache:indexeddb_unavailable", {});
    return Promise.resolve(null);
  }

  if (dbPromise) {
    return dbPromise;
  }

  dbPromise = new Promise((resolve, reject) => {
    const request = window.indexedDB.open(DB_NAME, DB_VERSION);

    request.onupgradeneeded = () => {
      const db = request.result;
      logImageEvent("cache:db_upgrade", {
        db_name: DB_NAME,
        db_version: DB_VERSION,
      });

      if (!db.objectStoreNames.contains(ASSETS_STORE)) {
        const assetsStore = db.createObjectStore(ASSETS_STORE, { keyPath: "id" });
        assetsStore.createIndex("cacheClass", "cacheClass", { unique: false });
        assetsStore.createIndex("lastUsedAt", "lastUsedAt", { unique: false });
        assetsStore.createIndex("updatedAt", "updatedAt", { unique: false });
      }

      if (!db.objectStoreNames.contains(BOOKS_STORE)) {
        const booksStore = db.createObjectStore(BOOKS_STORE, { keyPath: "id" });
        booksStore.createIndex("cacheClass", "cacheClass", { unique: false });
        booksStore.createIndex("lastUsedAt", "lastUsedAt", { unique: false });
        booksStore.createIndex("updatedAt", "updatedAt", { unique: false });
      }
    };

    request.onsuccess = () => {
      const db = request.result;
      attachDatabaseLifecycleHandlers(db);
      logImageEvent("cache:db_open_success", {
        db_name: DB_NAME,
        db_version: DB_VERSION,
      });
      resolve(db);
    };

    request.onerror = () => {
      resetDatabasePromise();
      logImageEvent("cache:db_open_error", {
        db_name: DB_NAME,
        db_version: DB_VERSION,
        error: request.error,
      });
      reject(request.error);
    };

    request.onblocked = () => {
      resetDatabasePromise();
      logImageEvent("cache:db_open_blocked", {
        db_name: DB_NAME,
        db_version: DB_VERSION,
      });
    };
  });

  return dbPromise;
};

const runTransaction = async (storeName, mode, operation, retryCount = 1) => {
  try {
    const db = await openDatabase();
    if (!db) {
      logImageEvent("cache:transaction_skipped", {
        store_name: storeName,
        mode,
      });
      return null;
    }

    return await new Promise((resolve, reject) => {
      let request = null;
      let resolved = false;
      const transaction = db.transaction(storeName, mode);
      const store = transaction.objectStore(storeName);

      transaction.oncomplete = () => {
        if (!resolved) {
          resolve(request?.result ?? null);
        }
      };

      transaction.onerror = () => reject(transaction.error);
      transaction.onabort = () => reject(transaction.error);

      request = operation(store);
      if (!request) {
        return;
      }

      request.onsuccess = () => {
        resolved = true;
        resolve(request.result);
      };
      request.onerror = () => reject(request.error);
    });
  } catch (error) {
    logImageEvent("cache:transaction_error", {
      store_name: storeName,
      mode,
      retry_count: retryCount,
      error,
    });
    if (retryCount > 0 && isRecoverableDatabaseError(error)) {
      resetDatabasePromise();
      return runTransaction(storeName, mode, operation, retryCount - 1);
    }

    throw error;
  }
};

const putRecord = (storeName, value) =>
  runTransaction(storeName, "readwrite", (store) => store.put(value));

const getRecord = (storeName, key) =>
  runTransaction(storeName, "readonly", (store) => store.get(key));

const deleteRecord = (storeName, key) =>
  runTransaction(storeName, "readwrite", (store) => store.delete(key));

const getAllRecords = (storeName) =>
  runTransaction(storeName, "readonly", (store) => store.getAll());

const fullBookKey = (bookId) => `book:${bookId}`;
const shelfCoverKey = (bookId) => `shelf-cover:${bookId}`;

const isExpired = (entry) => Boolean(entry?.expiresAt && entry.expiresAt < now());

const parseTimestamp = (value) => {
  if (value == null) {
    return null;
  }

  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }

  if (value instanceof Date) {
    const timestamp = value.getTime();
    return Number.isFinite(timestamp) ? timestamp : null;
  }

  const timestamp = Date.parse(value);
  return Number.isFinite(timestamp) ? timestamp : null;
};

export const isSignedUrlUsable = (expiresAt, { bufferMs = SIGNED_URL_EXPIRY_BUFFER_MS } = {}) => {
  const expiresAtMs = parseTimestamp(expiresAt);
  if (expiresAtMs == null) {
    return true;
  }

  return expiresAtMs - bufferMs > now();
};

const sanitizeShelfBook = (book = {}) => {
  const remoteCoverUrl = book.remote_cover_url ?? book.cover_url ?? book.cover?.url ?? null;
  const coverExpiresAt = book.remote_cover_expires_at ?? book.cover_expires_at ?? book.cover?.expires_at ?? null;
  const coverUrl = remoteCoverUrl && isSignedUrlUsable(coverExpiresAt) ? remoteCoverUrl : null;

  return {
    ...book,
    remote_cover_url: remoteCoverUrl,
    remote_cover_expires_at: coverExpiresAt,
    cover_url: coverUrl,
    cover_source_kind: coverUrl ? "remote" : "none",
  };
};

const toShelfMetadataBook = (book = {}) => {
  const remoteCoverUrl = book.remote_cover_url ?? book.cover_url ?? book.cover?.url ?? null;
  const remoteCoverExpiresAt =
    book.remote_cover_expires_at ?? book.cover_expires_at ?? book.cover?.expires_at ?? null;

  return {
    ...book,
    cover_url: remoteCoverUrl,
    cover_expires_at: remoteCoverExpiresAt,
    remote_cover_url: remoteCoverUrl,
    remote_cover_expires_at: remoteCoverExpiresAt,
    cover_source_kind: undefined,
    __shelfCoverObjectUrl: undefined,
  };
};

const deleteEntries = async (entries) => {
  await Promise.all(
    entries.map(async (entry) => {
      if (entry.storeName && entry.id) {
        await deleteRecord(entry.storeName, entry.id);
      }
    }),
  );
};

const estimateRecordSize = (record) => {
  if (!record) {
    return 0;
  }

  if (record.byteLength) {
    return record.byteLength;
  }

  if (record.arrayBuffer instanceof ArrayBuffer) {
    return record.arrayBuffer.byteLength;
  }

  try {
    return new Blob([JSON.stringify(record)]).size;
  } catch (error) {
    return 0;
  }
};

const isLegacyAssetRecord = (entry) => {
  if (!entry) {
    return false;
  }

  if (entry.cacheClass === CACHE_CLASS_SHELF_COVER) {
    return (
      entry.schemaVersion !== SHELF_COVER_SCHEMA_VERSION ||
      entry.blob != null ||
      !(entry.arrayBuffer instanceof ArrayBuffer)
    );
  }

  if (entry.cacheClass !== CACHE_CLASS_FULL_BOOK) {
    return false;
  }

  return (
    entry.schemaVersion !== FULL_BOOK_SCHEMA_VERSION ||
    entry.blob != null ||
    !(entry.arrayBuffer instanceof ArrayBuffer)
  );
};

const isLegacyBookRecord = (entry) =>
  entry?.cacheClass === CACHE_CLASS_FULL_BOOK && entry.schemaVersion !== FULL_BOOK_SCHEMA_VERSION;

const ensureCacheMaintenance = async () => {
  if (maintenanceComplete) {
    return;
  }

  if (maintenancePromise) {
    return maintenancePromise;
  }

  maintenancePromise = (async () => {
    const [assetRecords, bookRecords] = await Promise.all([
      getAllRecords(ASSETS_STORE),
      getAllRecords(BOOKS_STORE),
    ]);

    const assets = assetRecords ?? [];
    const books = bookRecords ?? [];
    const removals = [];

    assets.forEach((entry) => {
      if (isLegacyAssetRecord(entry)) {
        removals.push({
          storeName: ASSETS_STORE,
          id: entry.id,
        });
      }
    });

    books.forEach((entry) => {
      if (isLegacyBookRecord(entry)) {
        removals.push({
          storeName: BOOKS_STORE,
          id: entry.id,
        });

        (entry.assets ?? []).forEach((asset) => {
          if (asset?.key) {
            removals.push({
              storeName: ASSETS_STORE,
              id: asset.key,
            });
          }
        });
      }
    });

    if (removals.length > 0) {
      logImageEvent("cache:legacy_cleanup", {
        removal_count: removals.length,
      });
      await deleteEntries(removals);
    }

    maintenanceComplete = true;
  })();

  try {
    await maintenancePromise;
  } finally {
    maintenancePromise = null;
  }
};

const safeFetchAsset = async (url) => {
  const startedAt = now();
  const response = await fetch(url);
  if (!response.ok) {
    logImageEvent("cache:fetch_error", {
      source_url: url,
      status: response.status,
      duration_ms: now() - startedAt,
    });
    throw new Error(`Failed to fetch asset. status=${response.status}`);
  }

  const arrayBuffer = await response.arrayBuffer();
  const contentType = response.headers?.get?.("content-type") || null;
  logImageEvent("cache:fetch_success", {
    source_url: url,
    status: response.status,
    duration_ms: now() - startedAt,
    byte_length: arrayBuffer.byteLength,
    content_type: contentType,
  });

  return {
    arrayBuffer,
    contentType,
    byteLength: arrayBuffer.byteLength,
  };
};

const toObjectUrl = (blob, fallbackUrl = null, debugContext = {}) => {
  if (typeof URL?.createObjectURL !== "function") {
    logImageEvent("cache:object_url_fallback", {
      ...debugContext,
      fallback_url: fallbackUrl,
    });
    return fallbackUrl;
  }

  const objectUrl = URL.createObjectURL(blob);
  logImageEvent("cache:object_url_created", {
    ...debugContext,
    object_url: objectUrl,
    blob_size: blob?.size ?? null,
    blob_type: blob?.type ?? null,
    fallback_url: fallbackUrl,
  });
  return objectUrl;
};

export const loadShelfMetadataSync = () => {
  const entry = readLocalStorageJson(METADATA_KEY);
  if (!entry || !Array.isArray(entry.books)) {
    return null;
  }

  if (entry.version !== METADATA_CACHE_VERSION || isExpired(entry)) {
    return null;
  }

  return {
    ...entry,
    books: entry.books.map((book) => sanitizeShelfBook(book)),
  };
};

export const saveShelfMetadata = async (books) => {
  const entry = withExpiry(
    {
      version: METADATA_CACHE_VERSION,
      books: Array.isArray(books) ? books.map((book) => toShelfMetadataBook(book)) : [],
    },
    METADATA_TTL_MS,
  );

  writeLocalStorageJson(METADATA_KEY, entry);
  return entry;
};

const buildFullBookAssetEntries = async (book) => {
  const assetDescriptors = [];
  const coverUrl = book.cover?.url ?? book.cover_url ?? null;

  if (coverUrl) {
    assetDescriptors.push({
      key: `${fullBookKey(book.book_id)}:cover`,
      type: "cover",
      page: null,
      sourceUrl: coverUrl,
    });
  }

  for (const image of book.images ?? []) {
    if (!image?.url || typeof image.page !== "number") {
      continue;
    }

    assetDescriptors.push({
      key: `${fullBookKey(book.book_id)}:image:${image.page}`,
      type: "image",
      page: image.page,
      sourceUrl: image.url,
    });
  }

  const persistedAssetKeys = [];

  try {
    const assets = await Promise.all(
      assetDescriptors.map(async (asset) => {
        const { arrayBuffer, contentType, byteLength } = await safeFetchAsset(asset.sourceUrl);
        const entry = withExpiry(
          {
            id: asset.key,
            schemaVersion: FULL_BOOK_SCHEMA_VERSION,
            bookId: book.book_id,
            page: asset.page,
            sourceUrl: asset.sourceUrl,
            arrayBuffer,
            byteLength,
            contentType,
            cacheClass: CACHE_CLASS_FULL_BOOK,
            assetType: asset.type,
            lastUsedAt: now(),
          },
          FULL_BOOK_TTL_MS,
        );

        await putRecord(ASSETS_STORE, entry);
        persistedAssetKeys.push(asset.key);
        return {
          key: asset.key,
          type: asset.type,
          page: asset.page,
          sourceUrl: asset.sourceUrl,
        };
      }),
    );

    return assets;
  } catch (error) {
    await deleteEntries(
      persistedAssetKeys.map((assetKey) => ({
        storeName: ASSETS_STORE,
        id: assetKey,
      })),
    );
    throw error;
  }
};

const isValidShelfCoverRecord = (entry) =>
  entry?.cacheClass === CACHE_CLASS_SHELF_COVER &&
  entry.schemaVersion === SHELF_COVER_SCHEMA_VERSION &&
  !isExpired(entry) &&
  entry.arrayBuffer instanceof ArrayBuffer;

export const deleteShelfCover = async (bookId) => {
  if (!bookId) {
    return;
  }

  await deleteRecord(ASSETS_STORE, shelfCoverKey(bookId));
};

export const saveShelfCover = async (book) => {
  if (!book?.book_id) {
    return null;
  }

  const sourceUrl = book.remote_cover_url ?? book.cover_url ?? null;
  const coverExpiresAt = book.remote_cover_expires_at ?? book.cover_expires_at ?? null;
  if (!sourceUrl || !isSignedUrlUsable(coverExpiresAt)) {
    if (!sourceUrl) {
      await deleteShelfCover(book.book_id);
    }
    return null;
  }

  const db = await openDatabase();
  if (!db) {
    return null;
  }

  await ensureCacheMaintenance();

  const key = shelfCoverKey(book.book_id);
  const existingRecord = await getRecord(ASSETS_STORE, key);
  if (isValidShelfCoverRecord(existingRecord) && existingRecord.sourceUrl === sourceUrl) {
    existingRecord.lastUsedAt = now();
    await putRecord(ASSETS_STORE, existingRecord);
    return existingRecord;
  }

  const { arrayBuffer, contentType, byteLength } = await safeFetchAsset(sourceUrl);
  const entry = withExpiry(
    {
      id: key,
      schemaVersion: SHELF_COVER_SCHEMA_VERSION,
      bookId: book.book_id,
      sourceUrl,
      arrayBuffer,
      byteLength,
      contentType,
      cacheClass: CACHE_CLASS_SHELF_COVER,
      assetType: "cover",
      lastUsedAt: now(),
    },
    SHELF_COVER_TTL_MS,
  );

  await putRecord(ASSETS_STORE, entry);
  return entry;
};

export const getCachedShelfCovers = async (books = []) => {
  const db = await openDatabase();
  if (!db || !Array.isArray(books) || books.length === 0) {
    return new Map();
  }

  await ensureCacheMaintenance();

  const coverMap = new Map();
  await Promise.all(
    books.map(async (book) => {
      const bookId = book?.book_id;
      if (!bookId) {
        return;
      }

      const entry = await getRecord(ASSETS_STORE, shelfCoverKey(bookId));
      if (!isValidShelfCoverRecord(entry)) {
        if (entry?.id) {
          await deleteRecord(ASSETS_STORE, entry.id);
        }
        return;
      }

      const sourceUrl = book.remote_cover_url ?? book.cover_url ?? null;
      const sourceExpiry = book.remote_cover_expires_at ?? book.cover_expires_at ?? null;
      if (!sourceUrl && sourceExpiry == null) {
        return;
      }

      if (sourceUrl && entry.sourceUrl !== sourceUrl) {
        return;
      }

      entry.lastUsedAt = now();
      await putRecord(ASSETS_STORE, entry);

      const blob = new Blob([entry.arrayBuffer], {
        type: entry.contentType || "application/octet-stream",
      });
      const objectUrl = toObjectUrl(blob, sourceUrl, {
        book_id: bookId,
        source_url: entry.sourceUrl,
        origin: "getCachedShelfCovers",
      });

      coverMap.set(bookId, {
        objectUrl,
        sourceUrl: entry.sourceUrl,
      });
    }),
  );

  return coverMap;
};

const deleteFullBookPackage = async (packageRecord) => {
  if (!packageRecord) {
    return;
  }

  const removals = [
    {
      storeName: BOOKS_STORE,
      id: packageRecord.id,
    },
    ...(packageRecord.assets ?? [])
      .filter((asset) => asset?.key)
      .map((asset) => ({
        storeName: ASSETS_STORE,
        id: asset.key,
      })),
  ];

  await deleteEntries(removals);
};

export const saveFullBookPackage = async (book) => {
  if (!book?.book_id) {
    return null;
  }

  const db = await openDatabase();
  if (!db) {
    return null;
  }

  await ensureCacheMaintenance();

  const existingPackage = await getRecord(BOOKS_STORE, fullBookKey(book.book_id));
  const assets = await buildFullBookAssetEntries(book);
  if (existingPackage) {
    await deleteFullBookPackage(existingPackage);
  }
  const packageRecord = withExpiry(
    {
      id: fullBookKey(book.book_id),
      schemaVersion: FULL_BOOK_SCHEMA_VERSION,
      bookId: book.book_id,
      cacheClass: CACHE_CLASS_FULL_BOOK,
      lastUsedAt: now(),
      package: {
        ...book,
        cachedAt: now(),
      },
      assets,
    },
    FULL_BOOK_TTL_MS,
  );

  await putRecord(BOOKS_STORE, packageRecord);
  return packageRecord;
};

export const getCachedFullBook = async (bookId) => {
  const db = await openDatabase();
  if (!db) {
    return null;
  }

  await ensureCacheMaintenance();

  const packageRecord = await getRecord(BOOKS_STORE, fullBookKey(bookId));
  if (!packageRecord || !packageRecord.package) {
    return null;
  }

  if (packageRecord.schemaVersion !== FULL_BOOK_SCHEMA_VERSION || isExpired(packageRecord)) {
    await deleteFullBookPackage(packageRecord);
    logImageEvent("full_book:cache_invalidated", {
      book_id: bookId,
      reason: isExpired(packageRecord) ? "expired" : "schema_mismatch",
    });
    return null;
  }

  const assets = await Promise.all(
    (packageRecord.assets ?? []).map(async (asset) => {
      const entry = await getRecord(ASSETS_STORE, asset.key);
      if (
        !entry ||
        entry.schemaVersion !== FULL_BOOK_SCHEMA_VERSION ||
        isExpired(entry) ||
        !(entry.arrayBuffer instanceof ArrayBuffer)
      ) {
        return null;
      }

      entry.lastUsedAt = now();
      await putRecord(ASSETS_STORE, entry);

      const blob = new Blob([entry.arrayBuffer], {
        type: entry.contentType || "application/octet-stream",
      });
      const objectUrl = toObjectUrl(blob, entry.sourceUrl, {
        book_id: bookId,
        source_url: entry.sourceUrl,
        origin: "getCachedFullBook",
      });
      logImageEvent("full_book:asset_reconstructed", {
        book_id: bookId,
        asset_key: asset.key,
        asset_type: asset.type,
        page: asset.page,
        byte_length: entry.byteLength ?? entry.arrayBuffer.byteLength,
        content_type: entry.contentType || null,
      });

      return {
        ...asset,
        objectUrl,
      };
    }),
  );

  if (assets.some((asset) => asset === null)) {
    await deleteFullBookPackage(packageRecord);
    logImageEvent("full_book:cache_invalidated", {
      book_id: bookId,
      reason: "missing_asset",
    });
    return null;
  }

  packageRecord.lastUsedAt = now();
  await putRecord(BOOKS_STORE, packageRecord);

  const coverAsset = assets.find((asset) => asset.type === "cover");
  const imageAssetsByPage = new Map(
    assets.filter((asset) => asset.type === "image").map((asset) => [asset.page, asset.objectUrl]),
  );

  return {
    ...packageRecord.package,
    json_url: null,
    cover: packageRecord.package.cover
      ? {
          ...packageRecord.package.cover,
          url: coverAsset?.objectUrl ?? packageRecord.package.cover.url,
        }
      : packageRecord.package.cover,
    cover_url: coverAsset?.objectUrl ?? packageRecord.package.cover_url,
    images: (packageRecord.package.images ?? []).map((image) => ({
      ...image,
      url: imageAssetsByPage.get(image.page) ?? image.url,
    })),
    __cachedObjectUrls: assets.map((asset) => asset.objectUrl),
  };
};

export const enforceCacheBudget = async ({ maxBytes = FULL_BOOK_MAX_BYTES } = {}) => {
  await ensureCacheMaintenance();

  const [assetRecords, bookRecords] = await Promise.all([
    getAllRecords(ASSETS_STORE),
    getAllRecords(BOOKS_STORE),
  ]);

  const assets = assetRecords ?? [];
  const books = bookRecords ?? [];
  const assetEntriesById = new Map(assets.map((entry) => [entry.id, entry]));
  const packageRecords = books.filter(
    (entry) =>
      entry?.cacheClass === CACHE_CLASS_FULL_BOOK && entry.schemaVersion === FULL_BOOK_SCHEMA_VERSION,
  );

  const removals = [];
  let totalSize = 0;
  const packageSummaries = packageRecords.map((entry) => {
    const packageSize = estimateRecordSize(entry);
    const assetSize = (entry.assets ?? []).reduce((sum, asset) => {
      const assetEntry = assetEntriesById.get(asset.key);
      return sum + estimateRecordSize(assetEntry);
    }, 0);
    const size = packageSize + assetSize;

    totalSize += size;
    return {
      entry,
      size,
      expired: isExpired(entry),
      lastUsedAt: entry.lastUsedAt ?? entry.updatedAt ?? 0,
    };
  });

  packageSummaries.forEach((summary) => {
    if (summary.expired) {
      removals.push(summary.entry);
    }
  });

  if (removals.length > 0) {
    await Promise.all(removals.map((entry) => deleteFullBookPackage(entry)));
    logImageEvent("full_book:budget_cleanup", {
      expired_package_count: removals.length,
      total_size_before_eviction: totalSize,
    });
  }

  const activePackages = packageSummaries
    .filter((summary) => !summary.expired)
    .sort((left, right) => left.lastUsedAt - right.lastUsedAt);

  let activeSize = activePackages.reduce((sum, summary) => sum + summary.size, 0);
  const evictedBookIds = [];
  for (const summary of activePackages) {
    if (activeSize <= maxBytes) {
      break;
    }

    await deleteFullBookPackage(summary.entry);
    activeSize -= summary.size;
    evictedBookIds.push(summary.entry.bookId);
  }

  if (evictedBookIds.length > 0) {
    logImageEvent("full_book:budget_eviction", {
      evicted_book_ids: evictedBookIds,
      max_bytes: maxBytes,
      total_size_after_eviction: activeSize,
    });
  }
};

export const enforceShelfCoverBudget = async ({ maxBytes = SHELF_COVER_MAX_BYTES } = {}) => {
  await ensureCacheMaintenance();

  const assetRecords = (await getAllRecords(ASSETS_STORE)) ?? [];
  const coverRecords = assetRecords.filter(
    (entry) =>
      entry?.cacheClass === CACHE_CLASS_SHELF_COVER &&
      entry.schemaVersion === SHELF_COVER_SCHEMA_VERSION,
  );

  const expiredRecords = coverRecords.filter((entry) => isExpired(entry));
  if (expiredRecords.length > 0) {
    await Promise.all(expiredRecords.map((entry) => deleteRecord(ASSETS_STORE, entry.id)));
  }

  const activeRecords = coverRecords
    .filter((entry) => !isExpired(entry))
    .sort((left, right) => (left.lastUsedAt ?? left.updatedAt ?? 0) - (right.lastUsedAt ?? right.updatedAt ?? 0));

  let activeSize = activeRecords.reduce((sum, entry) => sum + estimateRecordSize(entry), 0);
  const evictedBookIds = [];
  for (const entry of activeRecords) {
    if (activeSize <= maxBytes) {
      break;
    }

    await deleteRecord(ASSETS_STORE, entry.id);
    activeSize -= estimateRecordSize(entry);
    evictedBookIds.push(entry.bookId);
  }

  if (expiredRecords.length > 0 || evictedBookIds.length > 0) {
    logImageEvent("shelf_cover:budget_cleanup", {
      expired_count: expiredRecords.length,
      evicted_book_ids: evictedBookIds,
      max_bytes: maxBytes,
      total_size_after_eviction: activeSize,
    });
  }
};
