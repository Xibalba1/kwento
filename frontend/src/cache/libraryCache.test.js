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
        remote_cover_url: "https://example.com/cover.png",
        cover_url: "blob:cached-cover",
      },
    ]);

    expect(saved.version).toBe(1);
    expect(saved.expiresAt - saved.updatedAt).toBe(7 * 24 * 60 * 60 * 1000);
    expect(saved.books[0].cover_url).toBe("https://example.com/cover.png");
    expect(libraryCache.loadShelfMetadataSync()).toEqual(
      expect.objectContaining({
        books: [
          expect.objectContaining({
            book_id: "book-meta",
            book_title: "Metadata Book",
            remote_cover_url: "https://example.com/cover.png",
            cover_url: "https://example.com/cover.png",
            cover_source_kind: "remote",
          }),
        ],
      }),
    );
  });

  test("suppresses stale cached shelf cover URLs while keeping metadata", async () => {
    const nowSpy = jest.spyOn(Date, "now").mockReturnValue(1_000_000);

    await libraryCache.saveShelfMetadata([
      {
        book_id: "book-meta",
        book_title: "Metadata Book",
        cover_url: "https://example.com/stale-cover.png",
        cover_expires_at: new Date(1_000_000 + 60_000).toISOString(),
      },
    ]);

    expect(libraryCache.loadShelfMetadataSync()).toEqual(
      expect.objectContaining({
        books: [
          expect.objectContaining({
            book_id: "book-meta",
            book_title: "Metadata Book",
            cover_url: null,
            cover_expires_at: new Date(1_000_000 + 60_000).toISOString(),
          }),
        ],
      }),
    );

    nowSpy.mockRestore();
  });

  test("reports signed URLs as stale within the five minute safety buffer", () => {
    const nowSpy = jest.spyOn(Date, "now").mockReturnValue(1_000_000);

    expect(libraryCache.isSignedUrlUsable(new Date(1_000_000 + 10 * 60 * 1000).toISOString())).toBe(
      true,
    );
    expect(libraryCache.isSignedUrlUsable(new Date(1_000_000 + 4 * 60 * 1000).toISOString())).toBe(
      false,
    );

    nowSpy.mockRestore();
  });

  test("saves and rehydrates shelf cover bytes independently from shelf metadata", async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      arrayBuffer: async () => makeArrayBuffer("shelf-cover"),
      headers: { get: () => "image/png" },
    });

    await libraryCache.saveShelfCover({
      book_id: "shelf-book-1",
      remote_cover_url: "https://example.com/shelf-cover.png",
      remote_cover_expires_at: new Date(Date.now() + 60 * 60 * 1000).toISOString(),
    });

    const covers = await libraryCache.getCachedShelfCovers([
      {
        book_id: "shelf-book-1",
        remote_cover_url: "https://example.com/shelf-cover.png",
      },
    ]);

    expect(covers.get("shelf-book-1")).toEqual(
      expect.objectContaining({
        objectUrl: "blob:generated-1",
        sourceUrl: "https://example.com/shelf-cover.png",
      }),
    );
  });

  test("replaces cached shelf cover bytes when the source URL changes", async () => {
    global.fetch
      .mockResolvedValueOnce({
        ok: true,
        arrayBuffer: async () => makeArrayBuffer("cover-a"),
        headers: { get: () => "image/png" },
      })
      .mockResolvedValueOnce({
        ok: true,
        arrayBuffer: async () => makeArrayBuffer("cover-b"),
        headers: { get: () => "image/png" },
      });

    await libraryCache.saveShelfCover({
      book_id: "shelf-book-2",
      remote_cover_url: "https://example.com/cover-a.png",
      remote_cover_expires_at: new Date(Date.now() + 60 * 60 * 1000).toISOString(),
    });
    await libraryCache.saveShelfCover({
      book_id: "shelf-book-2",
      remote_cover_url: "https://example.com/cover-b.png",
      remote_cover_expires_at: new Date(Date.now() + 60 * 60 * 1000).toISOString(),
    });

    const covers = await libraryCache.getCachedShelfCovers([
      {
        book_id: "shelf-book-2",
        remote_cover_url: "https://example.com/cover-b.png",
      },
    ]);

    expect(global.fetch).toHaveBeenCalledTimes(2);
    expect(covers.get("shelf-book-2")).toEqual(
      expect.objectContaining({
        objectUrl: "blob:generated-1",
        sourceUrl: "https://example.com/cover-b.png",
      }),
    );
  });

  test("deletes cached shelf covers when the shelf entry no longer has a cover", async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      arrayBuffer: async () => makeArrayBuffer("cover-a"),
      headers: { get: () => "image/png" },
    });

    await libraryCache.saveShelfCover({
      book_id: "shelf-book-3",
      remote_cover_url: "https://example.com/cover-a.png",
      remote_cover_expires_at: new Date(Date.now() + 60 * 60 * 1000).toISOString(),
    });
    await libraryCache.deleteShelfCover("shelf-book-3");

    const covers = await libraryCache.getCachedShelfCovers([
      {
        book_id: "shelf-book-3",
      },
    ]);

    expect(covers.has("shelf-book-3")).toBe(false);
  });

  test("evicts expired and least-recently-used shelf covers under the shelf cover budget", async () => {
    const nowSpy = jest.spyOn(Date, "now");
    nowSpy.mockReturnValue(1_000);

    global.fetch
      .mockResolvedValueOnce({
        ok: true,
        arrayBuffer: async () => makeArrayBuffer("a".repeat(8_000)),
        headers: { get: () => "image/png" },
      })
      .mockResolvedValueOnce({
        ok: true,
        arrayBuffer: async () => makeArrayBuffer("b".repeat(16)),
        headers: { get: () => "image/png" },
      })
      .mockResolvedValueOnce({
        ok: true,
        arrayBuffer: async () => makeArrayBuffer("cover"),
        headers: { get: () => "image/png" },
      });

    await libraryCache.saveShelfCover({
      book_id: "older-shelf-book",
      remote_cover_url: "https://example.com/older-shelf-cover.png",
      remote_cover_expires_at: new Date(1_000 + 60 * 60 * 1000).toISOString(),
    });

    nowSpy.mockReturnValue(2_000);

    await libraryCache.saveShelfCover({
      book_id: "newer-shelf-book",
      remote_cover_url: "https://example.com/newer-shelf-cover.png",
      remote_cover_expires_at: new Date(2_000 + 60 * 60 * 1000).toISOString(),
    });

    await libraryCache.saveFullBookPackage({
      book_id: "full-book-safe",
      book_title: "Full Book Safe",
      cover_url: "https://example.com/full-book-cover.png",
      images: [],
      pages: [],
    });

    await libraryCache.enforceShelfCoverBudget({ maxBytes: 1_000 });

    const shelfCovers = await libraryCache.getCachedShelfCovers([
      {
        book_id: "older-shelf-book",
        remote_cover_url: "https://example.com/older-shelf-cover.png",
      },
      {
        book_id: "newer-shelf-book",
        remote_cover_url: "https://example.com/newer-shelf-cover.png",
      },
    ]);

    expect(shelfCovers.has("older-shelf-book")).toBe(false);
    expect(shelfCovers.has("newer-shelf-book")).toBe(true);
    await expect(libraryCache.getCachedFullBook("full-book-safe")).resolves.not.toBeNull();

    nowSpy.mockRestore();
  });

  test("returns no cached shelf covers when indexedDB is unavailable", async () => {
    delete window.indexedDB;

    const covers = await libraryCache.getCachedShelfCovers([
      {
        book_id: "no-db-book",
        remote_cover_url: "https://example.com/cover.png",
      },
    ]);

    await expect(
      libraryCache.saveShelfCover({
        book_id: "no-db-book",
        remote_cover_url: "https://example.com/cover.png",
      }),
    ).resolves.toBeNull();
    expect(covers.size).toBe(0);
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

  test("preserves an existing full-book package when a replacement save fails", async () => {
    global.fetch
      .mockResolvedValueOnce({
        ok: true,
        arrayBuffer: async () => makeArrayBuffer("cover-a"),
        headers: { get: () => "image/png" },
      })
      .mockResolvedValueOnce({
        ok: true,
        arrayBuffer: async () => makeArrayBuffer("page-a"),
        headers: { get: () => "image/png" },
      });

    await libraryCache.saveFullBookPackage({
      book_id: "book-safe",
      book_title: "Original Book",
      cover_url: "https://example.com/original-cover.png",
      images: [
        {
          page: 1,
          url: "https://example.com/original-page-1.png",
        },
      ],
      pages: [
        {
          page_number: 1,
          content: {
            text_content_of_this_page: "Original page",
          },
        },
      ],
    });

    global.fetch.mockReset();
    global.fetch.mockResolvedValueOnce({
      ok: false,
      status: 400,
      arrayBuffer: async () => makeArrayBuffer(""),
      headers: { get: () => "image/png" },
    });

    await expect(
      libraryCache.saveFullBookPackage({
        book_id: "book-safe",
        book_title: "Replacement Book",
        cover_url: "https://example.com/replacement-cover.png",
        images: [],
        pages: [
          {
            page_number: 1,
            content: {
              text_content_of_this_page: "Replacement page",
            },
          },
        ],
      }),
    ).rejects.toThrow("Failed to fetch asset. status=400");

    const cachedBook = await libraryCache.getCachedFullBook("book-safe");

    expect(cachedBook).toEqual(
      expect.objectContaining({
        book_id: "book-safe",
        book_title: "Original Book",
      }),
    );
    expect(cachedBook.cover_url).toBe("blob:generated-1");
    expect(cachedBook.images[0].url).toBe("blob:generated-2");
  });
});
