import { logImageEvent } from "../debug/imageDebug";

const CACHE_VERSION = 1;
const TTL_MS = 7 * 24 * 60 * 60 * 1000;
const DB_NAME = "kwento-cache";
const DB_VERSION = 1;
const ASSETS_STORE = "assets";
const BOOKS_STORE = "books";
const METADATA_KEY = "kwento_shelf_metadata_v1";

const CACHE_CLASS_SHELF_COVER = "shelf-cover";
const CACHE_CLASS_FULL_BOOK = "full-book";

let dbPromise = null;

const hasLocalStorage = () => typeof window !== "undefined" && window.localStorage;
const hasIndexedDb = () => typeof window !== "undefined" && window.indexedDB;

const now = () => Date.now();

const withExpiry = (value = {}) => {
  const updatedAt = value.updatedAt ?? now();
  return {
    ...value,
    updatedAt,
    expiresAt: value.expiresAt ?? updatedAt + TTL_MS,
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

const safeFetchBlob = async (url) => {
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

  const blob = await response.blob();
  logImageEvent("cache:fetch_success", {
    source_url: url,
    status: response.status,
    duration_ms: now() - startedAt,
    blob_size: blob.size,
    content_type: blob.type || response.headers?.get?.("content-type") || null,
  });
  return blob;
};

const shelfCoverKey = (bookId) => `cover:${bookId}`;
const fullBookKey = (bookId) => `book:${bookId}`;

const isExpired = (entry) => Boolean(entry?.expiresAt && entry.expiresAt < now());

const approximateBlobSize = (blob) => blob?.size ?? 0;
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

const estimateRecordSize = (record) => {
  if (!record) {
    return 0;
  }

  if (record.blob) {
    return approximateBlobSize(record.blob);
  }

  try {
    return new Blob([JSON.stringify(record)]).size;
  } catch (error) {
    return 0;
  }
};

export const loadShelfMetadataSync = () => {
  const entry = readLocalStorageJson(METADATA_KEY);
  if (!entry || entry.version !== CACHE_VERSION || !Array.isArray(entry.books)) {
    return null;
  }

  return entry;
};

export const saveShelfMetadata = async (books) => {
  const entry = withExpiry({
    version: CACHE_VERSION,
    books: Array.isArray(books) ? books : [],
  });

  writeLocalStorageJson(METADATA_KEY, entry);
  return entry;
};

export const getCachedShelfCover = async (bookId, sourceUrl) => {
  const entry = await getRecord(ASSETS_STORE, shelfCoverKey(bookId));
  if (!entry || !entry.blob || isExpired(entry)) {
    logImageEvent("cover:get_cached_miss", {
      book_id: bookId,
      source_url: sourceUrl,
      cache_entry_present: Boolean(entry),
      expired: isExpired(entry),
    });
    console.debug(`[libraryCache] shelf cover miss for ${bookId}`);
    return null;
  }

  if (sourceUrl && entry.sourceUrl !== sourceUrl) {
    entry.sourceUrl = sourceUrl;
  }

  entry.lastUsedAt = now();
  await putRecord(ASSETS_STORE, entry);
  logImageEvent("cover:get_cached_hit", {
    book_id: bookId,
    source_url: sourceUrl,
    cached_source_url: entry.sourceUrl ?? null,
    blob_size: approximateBlobSize(entry.blob),
  });
  console.debug(
    `[libraryCache] shelf cover hit for ${bookId} via cached blob (${sourceUrl ? "remote-source-observed" : "no-source"})`,
  );
  return toObjectUrl(entry.blob, entry.sourceUrl ?? sourceUrl, {
    book_id: bookId,
    source_url: entry.sourceUrl ?? sourceUrl,
    origin: "getCachedShelfCover",
  });
};

export const hasCachedShelfCover = async (bookId, sourceUrl) => {
  const entry = await getRecord(ASSETS_STORE, shelfCoverKey(bookId));
  if (!entry || !entry.blob || isExpired(entry)) {
    logImageEvent("cover:has_cached_miss", {
      book_id: bookId,
      source_url: sourceUrl,
      cache_entry_present: Boolean(entry),
      expired: isExpired(entry),
    });
    console.debug(`[libraryCache] hasCachedShelfCover miss for ${bookId}`);
    return false;
  }

  if (sourceUrl && entry.sourceUrl !== sourceUrl) {
    entry.sourceUrl = sourceUrl;
    await putRecord(ASSETS_STORE, entry);
  }

  logImageEvent("cover:has_cached_hit", {
    book_id: bookId,
    source_url: sourceUrl,
    cached_source_url: entry.sourceUrl ?? null,
    blob_size: approximateBlobSize(entry.blob),
  });
  console.debug(`[libraryCache] hasCachedShelfCover hit for ${bookId}`);
  return true;
};

export const cacheShelfCover = async ({ bookId, sourceUrl }) => {
  if (!bookId || !sourceUrl) {
    logImageEvent("cover:cache_skip", {
      book_id: bookId,
      source_url: sourceUrl,
    });
    return null;
  }

  const db = await openDatabase();
  if (!db) {
    logImageEvent("cover:cache_bypass", {
      book_id: bookId,
      source_url: sourceUrl,
      reason: "no_indexeddb",
    });
    return sourceUrl;
  }

  const existing = await getRecord(ASSETS_STORE, shelfCoverKey(bookId));
  if (existing?.blob && !isExpired(existing)) {
    existing.sourceUrl = sourceUrl;
    existing.lastUsedAt = now();
    await putRecord(ASSETS_STORE, existing);
    logImageEvent("cover:cache_hit_reuse", {
      book_id: bookId,
      source_url: sourceUrl,
      blob_size: approximateBlobSize(existing.blob),
    });
    console.debug(`[libraryCache] shelf cover cache hit for ${bookId}; reusing cached blob`);
    return toObjectUrl(existing.blob, existing.sourceUrl, {
      book_id: bookId,
      source_url: existing.sourceUrl,
      origin: "cacheShelfCover:existing",
    });
  }

  const blob = await safeFetchBlob(sourceUrl);
  const entry = withExpiry({
    id: shelfCoverKey(bookId),
    bookId,
    sourceUrl,
    blob,
    cacheClass: CACHE_CLASS_SHELF_COVER,
    lastUsedAt: now(),
  });

  await putRecord(ASSETS_STORE, entry);
  logImageEvent("cover:cache_store", {
    book_id: bookId,
    source_url: sourceUrl,
    blob_size: approximateBlobSize(blob),
    expires_at: entry.expiresAt,
  });
  console.debug(`[libraryCache] shelf cover cache miss for ${bookId}; fetched remote asset`);
  return toObjectUrl(blob, sourceUrl, {
    book_id: bookId,
    source_url: sourceUrl,
    origin: "cacheShelfCover:fetched",
  });
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

  const assets = await Promise.all(
    assetDescriptors.map(async (asset) => {
      const blob = await safeFetchBlob(asset.sourceUrl);
      const entry = withExpiry({
        id: asset.key,
        bookId: book.book_id,
        page: asset.page,
        sourceUrl: asset.sourceUrl,
        blob,
        cacheClass: CACHE_CLASS_FULL_BOOK,
        assetType: asset.type,
        lastUsedAt: now(),
      });

      await putRecord(ASSETS_STORE, entry);
      return {
        key: asset.key,
        type: asset.type,
        page: asset.page,
        sourceUrl: asset.sourceUrl,
      };
    }),
  );

  return assets;
};

export const saveFullBookPackage = async (book) => {
  if (!book?.book_id) {
    return null;
  }

  const db = await openDatabase();
  if (!db) {
    return null;
  }

  const assets = await buildFullBookAssetEntries(book);
  const packageRecord = withExpiry({
    id: fullBookKey(book.book_id),
    bookId: book.book_id,
    cacheClass: CACHE_CLASS_FULL_BOOK,
    lastUsedAt: now(),
    package: {
      ...book,
      cachedAt: now(),
    },
    assets,
  });

  await putRecord(BOOKS_STORE, packageRecord);
  return packageRecord;
};

export const getCachedFullBook = async (bookId) => {
  const db = await openDatabase();
  if (!db) {
    return null;
  }

  const packageRecord = await getRecord(BOOKS_STORE, fullBookKey(bookId));
  if (!packageRecord || !packageRecord.package || isExpired(packageRecord)) {
    return null;
  }

  const assets = await Promise.all(
    (packageRecord.assets ?? []).map(async (asset) => {
      const entry = await getRecord(ASSETS_STORE, asset.key);
      if (!entry?.blob || isExpired(entry)) {
        return null;
      }

      entry.lastUsedAt = now();
      await putRecord(ASSETS_STORE, entry);
      return {
        ...asset,
        objectUrl: toObjectUrl(entry.blob, entry.sourceUrl),
      };
    }),
  );

  if (assets.some((asset) => asset === null)) {
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

const deleteEntries = async (entries) => {
  await Promise.all(
    entries.map(async (entry) => {
      if (entry.storeName && entry.id) {
        await deleteRecord(entry.storeName, entry.id);
      }
    }),
  );
};

export const enforceCacheBudget = async ({ maxBytes = 500 * 1024 * 1024 } = {}) => {
  const [assetRecords, bookRecords] = await Promise.all([
    getAllRecords(ASSETS_STORE),
    getAllRecords(BOOKS_STORE),
  ]);

  const assets = assetRecords ?? [];
  const books = bookRecords ?? [];
  const metadata = loadShelfMetadataSync();
  const metadataSize = metadata ? estimateRecordSize(metadata) : 0;

  const candidates = [
    ...books.map((entry) => ({ ...entry, storeName: BOOKS_STORE, size: estimateRecordSize(entry) })),
    ...assets.map((entry) => ({ ...entry, storeName: ASSETS_STORE, size: estimateRecordSize(entry) })),
  ];

  let totalSize = metadataSize + candidates.reduce((sum, entry) => sum + entry.size, 0);
  if (totalSize <= maxBytes) {
    return;
  }

  const evictionPriority = (entry) => {
    if (entry.cacheClass === CACHE_CLASS_FULL_BOOK) {
      return 0;
    }

    if (entry.cacheClass === CACHE_CLASS_SHELF_COVER) {
      return 1;
    }

    return 2;
  };

  const evictableEntries = candidates.sort((left, right) => {
    const classDelta = evictionPriority(left) - evictionPriority(right);
    if (classDelta !== 0) {
      return classDelta;
    }

    const leftExpired = isExpired(left) ? 0 : 1;
    const rightExpired = isExpired(right) ? 0 : 1;
    if (leftExpired !== rightExpired) {
      return leftExpired - rightExpired;
    }

    return (left.lastUsedAt ?? left.updatedAt ?? 0) - (right.lastUsedAt ?? right.updatedAt ?? 0);
  });

  const removals = [];
  for (const entry of evictableEntries) {
    if (totalSize <= maxBytes) {
      break;
    }

    removals.push(entry);
    totalSize -= entry.size;
  }

  await deleteEntries(removals);
};
