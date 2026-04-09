import React, { useCallback, useEffect, useRef, useState } from "react";
import ThemeInput from "./components/ThemeInput";
import BookModal from "./components/BookModal";
import BookList from "./components/BookList";
import { buildApiUrl } from "./config";
import {
  enforceCacheBudget,
  enforceShelfCoverBudget,
  getCachedShelfCovers,
  getCachedFullBook,
  deleteShelfCover,
  loadShelfMetadataSync,
  saveShelfCover,
  saveFullBookPackage,
  saveShelfMetadata,
} from "./cache/libraryCache";
import { getImageDebugPageContext, logImageEvent } from "./debug/imageDebug";
const releaseObjectUrls = (urls = []) => {
  if (typeof URL?.revokeObjectURL !== "function") {
    return;
  }

  urls.forEach((url) => {
    if (typeof url === "string" && url.startsWith("blob:")) {
      URL.revokeObjectURL(url);
    }
  });
};

const areBookIdListsEqual = (left = [], right = []) =>
  left.length === right.length && left.every((value, index) => value === right[index]);

const SHELF_COVER_WARM_CONCURRENCY = 2;

const normalizeLibraryFlags = (bookData = {}) => {
  const isArchived = Boolean(bookData.is_archived);
  const isFavorite = isArchived ? false : Boolean(bookData.is_favorite);

  return {
    is_archived: isArchived,
    is_favorite: isFavorite,
  };
};

const normalizeBook = (bookData = {}) => ({
  ...bookData,
  book_id: bookData.book_id,
  book_title: bookData.book_title,
  created_at: bookData.created_at ?? null,
  json_url: bookData.json_url,
  remote_cover_url: bookData.remote_cover_url ?? bookData.cover_url ?? bookData.cover?.url ?? null,
  remote_cover_expires_at:
    bookData.remote_cover_expires_at ?? bookData.cover_expires_at ?? bookData.cover?.expires_at ?? null,
  cover_url:
    bookData.cover_url ??
    bookData.remote_cover_url ??
    bookData.cover?.url ??
    null,
  cover_source_kind:
    bookData.cover_source_kind ??
    (bookData.cover_url ?? bookData.remote_cover_url ?? bookData.cover?.url ? "remote" : "none"),
  images: bookData.images ?? [],
  ...normalizeLibraryFlags(bookData),
});

const applyLibraryStateRules = (bookData = {}, updates = {}) => {
  const nextBook = {
    ...bookData,
    ...normalizeLibraryFlags(bookData),
    ...(updates.is_archived !== undefined ? { is_archived: Boolean(updates.is_archived) } : {}),
    ...(updates.is_favorite !== undefined ? { is_favorite: Boolean(updates.is_favorite) } : {}),
  };

  if (updates.is_archived === true) {
    nextBook.is_favorite = false;
  } else if (updates.is_favorite === true) {
    nextBook.is_archived = false;
  } else if (nextBook.is_archived) {
    nextBook.is_favorite = false;
  } else if (nextBook.is_favorite) {
    nextBook.is_archived = false;
  }

  return nextBook;
};

const mergeShelfCoverUrls = (books, coverMap) => {
  let changed = false;

  const nextBooks = books.map((book) => {
    const cachedCover = coverMap.get(book.book_id);
    const fallbackUrl = book.remote_cover_url ?? null;
    const nextCoverUrl = cachedCover?.objectUrl ?? fallbackUrl;
    const nextSourceKind = cachedCover ? "cache" : nextCoverUrl ? "remote" : "none";
    const nextObjectUrl = cachedCover?.objectUrl ?? null;

    if (
      book.cover_url === nextCoverUrl &&
      book.cover_source_kind === nextSourceKind &&
      (book.__shelfCoverObjectUrl ?? null) === nextObjectUrl
    ) {
      return book;
    }

    changed = true;
    return {
      ...book,
      cover_url: nextCoverUrl,
      cover_source_kind: nextSourceKind,
      __shelfCoverObjectUrl: nextObjectUrl,
    };
  });

  return changed ? nextBooks : books;
};

const runWithConcurrency = async (items, limit, task) => {
  const workerCount = Math.max(1, Math.min(limit, items.length));
  let index = 0;

  await Promise.all(
    Array.from({ length: workerCount }, async () => {
      while (index < items.length) {
        const currentIndex = index;
        index += 1;
        await task(items[currentIndex]);
      }
    }),
  );
};

const App = () => {
  const [theme, setTheme] = useState("");
  const [book, setBook] = useState(null);
  const [loading, setLoading] = useState(false);
  const [, setExistingBookLoading] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [libraryBooks, setLibraryBooks] = useState([]);
  const [libraryLoading, setLibraryLoading] = useState(false);
  const [libraryError, setLibraryError] = useState(false);
  const [activeFullBookWorkCount, setActiveFullBookWorkCount] = useState(0);
  const [pendingLibraryStateBookIds, setPendingLibraryStateBookIds] = useState([]);
  const [, setVisibleBookIds] = useState([]);
  const libraryFetchPromiseRef = useRef(null);
  const cachedBookObjectUrlsRef = useRef([]);
  const previousBookObjectUrlsRef = useRef([]);
  const previousShelfCoverUrlsRef = useRef(new Map());
  const inFlightBookSelectionRef = useRef(new Map());
  const visibleBookIdsRef = useRef([]);
  const warmedShelfCoverKeysRef = useRef(new Set());
  const shelfCoverCacheKey = libraryBooks
    .map(
      (bookEntry) =>
        `${bookEntry.book_id}:${bookEntry.remote_cover_url ?? ""}:${bookEntry.remote_cover_expires_at ?? ""}`,
    )
    .join("|");
  const shelfCoverSnapshotJson = JSON.stringify(
    libraryBooks.map((bookEntry) => ({
      book_id: bookEntry.book_id,
      remote_cover_url: bookEntry.remote_cover_url,
      remote_cover_expires_at: bookEntry.remote_cover_expires_at,
      cover_url: bookEntry.remote_cover_url,
    })),
  );

  const runWithFullBookWork = useCallback(async (work) => {
    setActiveFullBookWorkCount((count) => count + 1);
    try {
      return await work();
    } finally {
      setActiveFullBookWorkCount((count) => Math.max(0, count - 1));
    }
  }, []);

  const cacheFullBookInBackground = async (completeBookData) => {
    try {
      await runWithFullBookWork(async () => {
        await saveFullBookPackage(completeBookData);
        await enforceCacheBudget();
      });
      logImageEvent("full_book:cache_saved", {
        book_id: completeBookData.book_id,
        image_count: completeBookData.images?.length ?? 0,
      });
    } catch (error) {
      console.warn("Failed to cache full book package:", error);
      logImageEvent("full_book:cache_save_error", {
        book_id: completeBookData?.book_id ?? null,
        error,
      });
    }
  };

  const upsertBookInLibrary = (bookData) => {
    if (!bookData?.book_id) {
      return;
    }

    setLibraryBooks((previousBooks) => {
      const existingIndex = previousBooks.findIndex(
        (existingBook) => existingBook.book_id === bookData.book_id,
      );

      const normalizedBook = normalizeBook(bookData);

      if (existingIndex >= 0) {
        const nextBooks = [...previousBooks];
        nextBooks[existingIndex] = { ...nextBooks[existingIndex], ...normalizedBook };
        return nextBooks;
      }

      return [normalizedBook, ...previousBooks];
    });
  };

  const fetchLibraryBooks = useCallback(async ({ force = false } = {}) => {
    if (libraryFetchPromiseRef.current && !force) {
      return libraryFetchPromiseRef.current;
    }

    const fetchPromise = (async () => {
      logImageEvent("shelf:fetch_start", {
        force,
      });
      setLibraryLoading(true);
      setLibraryError(false);

      try {
        const response = await fetch(buildApiUrl("/books/"), {
          method: "GET",
          headers: { "Content-Type": "application/json" },
        });

        if (!response.ok) {
          throw new Error(`Failed to fetch books. status=${response.status}`);
        }

        const books = await response.json();
        const normalizedBooks = Array.isArray(books) ? books.map((entry) => normalizeBook(entry)) : [];
        setLibraryBooks(normalizedBooks);
        await Promise.all(
          normalizedBooks.map((bookEntry) => {
            if (bookEntry.remote_cover_url) {
              return Promise.resolve();
            }

            return deleteShelfCover(bookEntry.book_id).catch(() => null);
          }),
        );
        logImageEvent("shelf:fetch_success", {
          count: normalizedBooks.length,
        });
        await saveShelfMetadata(normalizedBooks);
      } catch (error) {
        console.error("Failed to prefetch library books:", error);
        logImageEvent("shelf:fetch_error", {
          error,
        });
        setLibraryError(true);
      } finally {
        setLibraryLoading(false);
      }
    })();

    libraryFetchPromiseRef.current = fetchPromise;

    try {
      await fetchPromise;
    } finally {
      libraryFetchPromiseRef.current = null;
    }
  }, []);

  const fetchAndBuildFullBook = async (bookId) => {
    const response = await fetch(buildApiUrl(`/books/${bookId}/`), {
      method: "GET",
      headers: { "Content-Type": "application/json" },
    });

    if (!response.ok) {
      throw new Error("Failed to fetch the selected book");
    }

    const data = await response.json();
    const bookDataResponse = await fetch(data.json_url);
    if (!bookDataResponse.ok) {
      throw new Error("Failed to fetch book data from json_url");
    }

    const bookData = await bookDataResponse.json();

    return {
      ...data,
      ...bookData,
      json_url: data.json_url,
      cover: data.cover ?? bookData.cover ?? null,
      cover_url: data.cover?.url ?? data.cover_url ?? null,
      images: data.images ?? bookData.images ?? [],
      is_archived: Boolean(data.is_archived ?? bookData.is_archived),
      is_favorite: Boolean(data.is_favorite ?? bookData.is_favorite),
    };
  };

  useEffect(() => {
    logImageEvent("app:mount", getImageDebugPageContext());
    const cachedMetadata = loadShelfMetadataSync();
    if (cachedMetadata?.books?.length) {
      setLibraryBooks(cachedMetadata.books.map((entry) => normalizeBook(entry)));
      logImageEvent("shelf:metadata_hydrated", {
        count: cachedMetadata.books.length,
      });
    }

    fetchLibraryBooks();
  }, [fetchLibraryBooks]);

  useEffect(() => {
    const logLifecycleEvent = (eventName) => {
      logImageEvent(eventName, getImageDebugPageContext());
    };

    const handleVisibilityChange = () => {
      logLifecycleEvent("app:visibility_change");
    };
    const handlePageShow = () => {
      logLifecycleEvent("app:pageshow");
    };
    const handlePageHide = () => {
      logLifecycleEvent("app:pagehide");
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    window.addEventListener("pageshow", handlePageShow);
    window.addEventListener("pagehide", handlePageHide);

    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      window.removeEventListener("pageshow", handlePageShow);
      window.removeEventListener("pagehide", handlePageHide);
    };
  }, []);

  useEffect(() => {
    void saveShelfMetadata(libraryBooks);
  }, [libraryBooks]);

  useEffect(() => {
    return () => {
      releaseObjectUrls(cachedBookObjectUrlsRef.current);
      releaseObjectUrls(Array.from(previousShelfCoverUrlsRef.current.values()));
    };
  }, []);

  useEffect(() => {
    let isCancelled = false;
    const booksSnapshot = JSON.parse(shelfCoverSnapshotJson);

    const loadShelfCoverUrls = async () => {
      try {
        const cachedShelfCovers = await getCachedShelfCovers(booksSnapshot);
        if (isCancelled) {
          releaseObjectUrls(Array.from(cachedShelfCovers.values()).map((entry) => entry.objectUrl));
          return;
        }

        setLibraryBooks((currentBooks) => mergeShelfCoverUrls(currentBooks, cachedShelfCovers));
      } catch (error) {
        console.warn("Failed to read cached shelf covers:", error);
      }
    };

    if (booksSnapshot.length > 0) {
      void loadShelfCoverUrls();
    }

    return () => {
      isCancelled = true;
    };
  }, [shelfCoverCacheKey, shelfCoverSnapshotJson]);

  useEffect(() => {
    const previousUrls = previousShelfCoverUrlsRef.current;
    const nextUrls = new Map(
      libraryBooks
        .filter((bookEntry) => typeof bookEntry.__shelfCoverObjectUrl === "string")
        .map((bookEntry) => [bookEntry.book_id, bookEntry.__shelfCoverObjectUrl]),
    );

    previousUrls.forEach((url, bookId) => {
      if (nextUrls.get(bookId) !== url) {
        releaseObjectUrls([url]);
      }
    });

    previousShelfCoverUrlsRef.current = nextUrls;
  }, [libraryBooks]);

  useEffect(() => {
    if (libraryBooks.length === 0 || activeFullBookWorkCount > 0) {
      return undefined;
    }

    let cancelled = false;
    const timeoutId = window.setTimeout(() => {
      void (async () => {
        const candidateBooks = libraryBooks.filter((bookEntry) => {
          const coverUrl = bookEntry.remote_cover_url;
          if (!coverUrl || bookEntry.cover_source_kind === "cache") {
            return false;
          }

          const warmKey = `${bookEntry.book_id}:${coverUrl}`;
          if (warmedShelfCoverKeysRef.current.has(warmKey)) {
            return false;
          }

          return true;
        });

        await runWithConcurrency(candidateBooks, SHELF_COVER_WARM_CONCURRENCY, async (bookEntry) => {
          if (cancelled || activeFullBookWorkCount > 0) {
            return;
          }

          const warmKey = `${bookEntry.book_id}:${bookEntry.remote_cover_url}`;
          warmedShelfCoverKeysRef.current.add(warmKey);

          try {
            await saveShelfCover(bookEntry);
          } catch (error) {
            console.warn(`Failed to warm shelf cover for book ${bookEntry.book_id}:`, error);
          }
        });

        if (!cancelled) {
          try {
            await enforceShelfCoverBudget();
          } catch (error) {
            console.warn("Failed to enforce shelf cover budget:", error);
          }
        }
      })();
    }, 0);

    return () => {
      cancelled = true;
      window.clearTimeout(timeoutId);
    };
  }, [activeFullBookWorkCount, libraryBooks]);

  useEffect(() => {
    if (typeof URL?.revokeObjectURL !== "function") {
      previousBookObjectUrlsRef.current = book?.__cachedObjectUrls ?? [];
      cachedBookObjectUrlsRef.current = book?.__cachedObjectUrls ?? [];
      return;
    }

    const previousUrls = previousBookObjectUrlsRef.current;
    const nextUrls = book?.__cachedObjectUrls ?? [];
    const activeUrls = new Set(nextUrls);

    previousUrls.forEach((url) => {
      if (typeof url === "string" && url.startsWith("blob:") && !activeUrls.has(url)) {
        console.debug(`[App] Revoking stale book object URL: ${url}`);
        logImageEvent("book:object_url_revoked", {
          object_url: url,
          reason: "stale_book_asset",
        });
        URL.revokeObjectURL(url);
      }
    });

    previousBookObjectUrlsRef.current = nextUrls;
    cachedBookObjectUrlsRef.current = nextUrls;
  }, [book]);

  const openBook = (nextBook) => {
    setBook(nextBook);
    setIsModalOpen(true);
  };

  const handleVisibleBooksChange = useCallback((nextVisibleBookIds) => {
    const normalizedIds = Array.isArray(nextVisibleBookIds) ? nextVisibleBookIds : [];
    if (areBookIdListsEqual(visibleBookIdsRef.current, normalizedIds)) {
      return;
    }

    visibleBookIdsRef.current = normalizedIds;
    setVisibleBookIds(normalizedIds);
  }, []);

  const handleGenerateBook = async () => {
    if (!theme.trim()) {
      alert("Please enter a theme to generate a book.");
      return;
    }

    setLoading(true);
    setBook(null);

    try {
      await runWithFullBookWork(async () => {
        const response = await fetch(buildApiUrl("/books/"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ theme }),
        });

        if (!response.ok) {
          alert("Error generating book. Please try again.");
          return;
        }

        const data = await response.json();
        const bookDataResponse = await fetch(data.json_url);
        if (!bookDataResponse.ok) {
          throw new Error("Failed to fetch book data from json_url");
        }

        const bookData = await bookDataResponse.json();
        const completeBookData = normalizeBook({
          ...data,
          ...bookData,
          cover_url: data.cover?.url ?? data.cover_url ?? null,
          is_archived: Boolean(data.is_archived ?? bookData.is_archived),
          is_favorite: Boolean(data.is_favorite ?? bookData.is_favorite),
        });

        openBook(completeBookData);
        upsertBookInLibrary(completeBookData);
        void cacheFullBookInBackground(completeBookData);
      });
    } catch (error) {
      console.error(error);
      setBook(null);
      alert("Error generating book. Please try again.");
    } finally {
      setTheme("");
      setLoading(false);
    }
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
    setBook(null);
  };

  const handleUpdateLibraryState = async (bookId, updates) => {
    if (!bookId) {
      return;
    }

    setPendingLibraryStateBookIds((current) =>
      current.includes(bookId) ? current : [...current, bookId],
    );

    const previousBook = libraryBooks.find((entry) => entry.book_id === bookId) ?? null;
    const optimisticBook = previousBook ? normalizeBook(applyLibraryStateRules(previousBook, updates)) : null;

    setLibraryBooks((currentBooks) =>
      currentBooks.map((entry) =>
        entry.book_id === bookId ? normalizeBook(applyLibraryStateRules(entry, updates)) : entry,
      ),
    );
    setBook((currentBook) =>
      currentBook?.book_id === bookId
        ? normalizeBook(applyLibraryStateRules(currentBook, updates))
        : currentBook,
    );

    try {
      const response = await fetch(buildApiUrl(`/books/${bookId}/library-state/`), {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updates),
      });

      if (!response.ok) {
        throw new Error(`Failed to update library state. status=${response.status}`);
      }

      const updatedBook = normalizeBook(await response.json());
      setLibraryBooks((currentBooks) =>
        currentBooks.map((entry) => (entry.book_id === bookId ? { ...entry, ...updatedBook } : entry)),
      );
      setBook((currentBook) =>
          currentBook?.book_id === bookId
            ? { ...currentBook, ...updatedBook }
            : currentBook,
      );
    } catch (error) {
      console.error(`Failed to update library state for book ${bookId}:`, error);
      if (previousBook) {
        setLibraryBooks((currentBooks) =>
          currentBooks.map((entry) => (entry.book_id === bookId ? { ...entry, ...previousBook } : entry)),
        );
        setBook((currentBook) =>
          currentBook?.book_id === bookId
            ? { ...currentBook, ...previousBook }
            : currentBook,
        );
      } else if (optimisticBook) {
        setBook((currentBook) =>
          currentBook?.book_id === bookId
            ? { ...currentBook, ...optimisticBook }
            : currentBook,
        );
      }
      alert("Error updating library state. Please try again.");
    } finally {
      setPendingLibraryStateBookIds((current) => current.filter((entry) => entry !== bookId));
    }
  };

  const handleSelectBook = async (bookId) => {
    if (!bookId) {
      return;
    }

    const existingSelection = inFlightBookSelectionRef.current.get(bookId);
    if (existingSelection) {
      return existingSelection;
    }

    const selectionPromise = (async () => {
      setExistingBookLoading(true);
      setBook(null);

      try {
        await runWithFullBookWork(async () => {
          const cachedBook = await getCachedFullBook(bookId);
          if (cachedBook) {
            logImageEvent("full_book:cache_hit", {
              book_id: bookId,
            });
            openBook(normalizeBook(cachedBook));
            return;
          }

          logImageEvent("full_book:cache_miss", {
            book_id: bookId,
          });
          const completeBookData = normalizeBook(await fetchAndBuildFullBook(bookId));
          openBook(completeBookData);
          upsertBookInLibrary(completeBookData);
          void cacheFullBookInBackground(completeBookData);
        });
      } catch (error) {
        console.error(
          `App.js::handleSelectBook(): Failed to get book ID ${bookId} with error`,
          error,
        );
        logImageEvent("full_book:open_error", {
          book_id: bookId,
          error,
        });
        setBook(null);
        alert("Error fetching the book. Please try again.");
      } finally {
        setExistingBookLoading(false);
      }
    })();

    inFlightBookSelectionRef.current.set(bookId, selectionPromise);

    try {
      await selectionPromise;
    } finally {
      inFlightBookSelectionRef.current.delete(bookId);
    }

    return selectionPromise;
  };

  return (
    <div style={styles.container}>
      <h1 style={styles.mainTitle}>Kwento</h1>
      <h2 style={styles.subTitle}>Make your story!</h2>
      <ThemeInput
        theme={theme}
        setTheme={setTheme}
        onSubmit={handleGenerateBook}
        loading={loading}
      />
      <BookList
        books={libraryBooks}
        loading={libraryLoading && libraryBooks.length === 0}
        error={libraryError && libraryBooks.length === 0}
        onRetry={() => fetchLibraryBooks({ force: true })}
        onSelectBook={handleSelectBook}
        onVisibleBooksChange={handleVisibleBooksChange}
        onUpdateLibraryState={handleUpdateLibraryState}
        pendingLibraryStateBookIds={pendingLibraryStateBookIds}
      />

      {isModalOpen && book && (
        <BookModal
          book={book}
          onClose={handleCloseModal}
        />
      )}
    </div>
  );
};

const styles = {
  container: {
    minHeight: "100vh",
    padding: "32px 20px 48px",
    boxSizing: "border-box",
  },
  mainTitle: {
    textAlign: "center",
    fontSize: "48px",
    margin: "0",
    marginBottom: "8px",
    color: "#ffcc00",
    textShadow: "#FC0 1px 0 1px",
  },
  subTitle: {
    textAlign: "center",
    fontSize: "24px",
    marginTop: 0,
    marginBottom: "24px",
    color: "#ffcc00",
    textShadow: "#FC0 1px 0 1px",
  },
};

export default App;
