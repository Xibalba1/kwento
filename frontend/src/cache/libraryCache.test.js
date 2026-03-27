const createIndexedDbRequest = (transaction, resolver) => {
  const request = {};

  queueMicrotask(() => {
    request.result = resolver();
    if (typeof request.onsuccess === "function") {
      request.onsuccess({ target: request });
    }
    if (typeof transaction.oncomplete === "function") {
      transaction.oncomplete();
    }
  });

  return request;
};

const createFakeIndexedDb = () => {
  const stores = new Map();
  const objectStoreNames = {
    contains: (name) => stores.has(name),
  };

  const db = {
    objectStoreNames,
    createObjectStore: (name) => {
      stores.set(name, new Map());
      return {
        createIndex: () => {},
      };
    },
    close: jest.fn(),
    transaction: (storeName) => {
      const store = stores.get(storeName);
      const transaction = {
        oncomplete: null,
        onerror: null,
        onabort: null,
        objectStore: () => ({
          get: (key) => createIndexedDbRequest(transaction, () => store.get(key) ?? null),
          put: (value) =>
            createIndexedDbRequest(transaction, () => {
              store.set(value.id, value);
              return value;
            }),
          delete: (key) =>
            createIndexedDbRequest(transaction, () => {
              store.delete(key);
              return undefined;
            }),
          getAll: () => createIndexedDbRequest(transaction, () => Array.from(store.values())),
        }),
      };

      return transaction;
    },
  };

  return {
    open: () => {
      const request = {};

      queueMicrotask(() => {
        request.result = db;
        if (stores.size === 0 && typeof request.onupgradeneeded === "function") {
          request.onupgradeneeded({ target: request });
        }
        if (typeof request.onsuccess === "function") {
          request.onsuccess({ target: request });
        }
      });

      return request;
    },
  };
};

describe("libraryCache shelf cover identity", () => {
  let libraryCache;
  let createObjectUrlCount;

  beforeEach(() => {
    jest.resetModules();
    createObjectUrlCount = 0;

    global.fetch = jest.fn();
    global.URL.createObjectURL = jest.fn(() => {
      createObjectUrlCount += 1;
      return `blob:generated-${createObjectUrlCount}`;
    });
    global.URL.revokeObjectURL = jest.fn();
    window.indexedDB = createFakeIndexedDb();

    libraryCache = require("./libraryCache");
  });

  test("reuses a cached shelf cover even when the presigned URL changes", async () => {
    const blob = new Blob(["cover-bytes"]);
    global.fetch.mockResolvedValueOnce({
      ok: true,
      blob: async () => blob,
    });

    const firstObjectUrl = await libraryCache.cacheShelfCover({
      bookId: "book-1",
      sourceUrl: "https://example.com/cover.png?sig=one",
    });
    const secondObjectUrl = await libraryCache.cacheShelfCover({
      bookId: "book-1",
      sourceUrl: "https://example.com/cover.png?sig=two",
    });

    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(firstObjectUrl).toBe("blob:generated-1");
    expect(secondObjectUrl).toBe("blob:generated-2");
  });

  test("treats a rotated presigned URL as a cache hit for lookup helpers", async () => {
    const blob = new Blob(["cover-bytes"]);
    global.fetch.mockResolvedValueOnce({
      ok: true,
      blob: async () => blob,
    });

    await libraryCache.cacheShelfCover({
      bookId: "book-2",
      sourceUrl: "https://example.com/cover.png?sig=one",
    });

    await expect(
      libraryCache.hasCachedShelfCover("book-2", "https://example.com/cover.png?sig=two"),
    ).resolves.toBe(true);

    await expect(
      libraryCache.getCachedShelfCover("book-2", "https://example.com/cover.png?sig=three"),
    ).resolves.toBe("blob:generated-2");
  });
});
