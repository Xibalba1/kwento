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

const makeArrayBuffer = (value) => Uint8Array.from(value.split("").map((char) => char.charCodeAt(0))).buffer;

describe("libraryCache full-book persistence", () => {
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
    window.localStorage.clear();

    libraryCache = require("./libraryCache");
  });

  test("saves and rehydrates a full book package using ArrayBuffer asset records", async () => {
    global.fetch
      .mockResolvedValueOnce({
        ok: true,
        arrayBuffer: async () => makeArrayBuffer("cover-bytes"),
        headers: { get: () => "image/png" },
      })
      .mockResolvedValueOnce({
        ok: true,
        arrayBuffer: async () => makeArrayBuffer("page-bytes"),
        headers: { get: () => "image/png" },
      });

    await libraryCache.saveFullBookPackage({
      book_id: "book-1",
      book_title: "Cached Book",
      cover_url: "https://example.com/cover.png",
      images: [
        {
          page: 1,
          url: "https://example.com/page-1.png",
        },
      ],
      pages: [
        {
          page_number: 1,
          content: {
            text_content_of_this_page: "Page one",
          },
        },
      ],
    });

    const cachedBook = await libraryCache.getCachedFullBook("book-1");

    expect(global.fetch).toHaveBeenCalledTimes(2);
    expect(cachedBook.cover_url).toBe("blob:generated-1");
    expect(cachedBook.images[0].url).toBe("blob:generated-2");
    expect(cachedBook.__cachedObjectUrls).toEqual(["blob:generated-1", "blob:generated-2"]);
  });

  test("keeps shelf metadata in localStorage with a 7 day freshness window", async () => {
    const saved = await libraryCache.saveShelfMetadata([
      {
        book_id: "book-meta",
        book_title: "Metadata Book",
      },
    ]);

    expect(saved.version).toBe(1);
    expect(saved.expiresAt - saved.updatedAt).toBe(7 * 24 * 60 * 60 * 1000);
    expect(libraryCache.loadShelfMetadataSync()).toEqual(saved);
  });

  test("evicts expired and least-recently-used full book packages under the budget", async () => {
    const nowSpy = jest.spyOn(Date, "now");
    nowSpy.mockReturnValue(1_000);

    global.fetch
      .mockResolvedValueOnce({
        ok: true,
        arrayBuffer: async () => makeArrayBuffer("a".repeat(5_000)),
        headers: { get: () => "image/png" },
      })
      .mockResolvedValueOnce({
        ok: true,
        arrayBuffer: async () => makeArrayBuffer("b".repeat(16)),
        headers: { get: () => "image/png" },
      });

    await libraryCache.saveFullBookPackage({
      book_id: "older-book",
      book_title: "Older Book",
      cover_url: "https://example.com/older-cover.png",
      images: [],
      pages: [],
    });

    nowSpy.mockReturnValue(2_000);

    await libraryCache.saveFullBookPackage({
      book_id: "newer-book",
      book_title: "Newer Book",
      cover_url: "https://example.com/newer-cover.png",
      images: [],
      pages: [],
    });

    await libraryCache.enforceCacheBudget({ maxBytes: 1_000 });

    await expect(libraryCache.getCachedFullBook("older-book")).resolves.toBeNull();
    await expect(libraryCache.getCachedFullBook("newer-book")).resolves.not.toBeNull();

    nowSpy.mockRestore();
  });
});
