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

const openDatabase = () => {
  if (!hasIndexedDb()) {
    return Promise.resolve(null);
  }

  if (dbPromise) {
    return dbPromise;
  }

  dbPromise = new Promise((resolve, reject) => {
    const request = window.indexedDB.open(DB_NAME, DB_VERSION);

    request.onupgradeneeded = () => {
      const db = request.result;

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

    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });

  return dbPromise;
};

const runTransaction = async (storeName, mode, operation) => {
  const db = await openDatabase();
  if (!db) {
    return null;
  }

  return new Promise((resolve, reject) => {
    const transaction = db.transaction(storeName, mode);
    const store = transaction.objectStore(storeName);
    const request = operation(store);

    if (!request) {
      transaction.oncomplete = () => resolve(null);
      transaction.onerror = () => reject(transaction.error);
      return;
    }

    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
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
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch asset. status=${response.status}`);
  }

  return response.blob();
};

const shelfCoverKey = (bookId) => `cover:${bookId}`;
const fullBookKey = (bookId) => `book:${bookId}`;

const isExpired = (entry) => Boolean(entry?.expiresAt && entry.expiresAt < now());

const approximateBlobSize = (blob) => blob?.size ?? 0;
const toObjectUrl = (blob, fallbackUrl = null) => {
  if (typeof URL?.createObjectURL !== "function") {
    return fallbackUrl;
  }

  return URL.createObjectURL(blob);
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
    return null;
  }

  if (sourceUrl && entry.sourceUrl && entry.sourceUrl !== sourceUrl) {
    return null;
  }

  entry.lastUsedAt = now();
  await putRecord(ASSETS_STORE, entry);
  return toObjectUrl(entry.blob, entry.sourceUrl ?? sourceUrl);
};

export const hasCachedShelfCover = async (bookId, sourceUrl) => {
  const entry = await getRecord(ASSETS_STORE, shelfCoverKey(bookId));
  if (!entry || !entry.blob || isExpired(entry)) {
    return false;
  }

  return !sourceUrl || !entry.sourceUrl || entry.sourceUrl === sourceUrl;
};

export const cacheShelfCover = async ({ bookId, sourceUrl }) => {
  if (!bookId || !sourceUrl) {
    return null;
  }

  const db = await openDatabase();
  if (!db) {
    return sourceUrl;
  }

  const existing = await getRecord(ASSETS_STORE, shelfCoverKey(bookId));
  if (existing?.blob && !isExpired(existing) && existing.sourceUrl === sourceUrl) {
    existing.lastUsedAt = now();
    await putRecord(ASSETS_STORE, existing);
    return toObjectUrl(existing.blob, existing.sourceUrl);
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
  return toObjectUrl(blob, sourceUrl);
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
