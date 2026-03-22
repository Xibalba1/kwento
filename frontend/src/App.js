import React, { useEffect, useMemo, useRef, useState } from "react";
import ThemeInput from "./components/ThemeInput";
import BookModal from "./components/BookModal";
import BookList from "./components/BookList";
import { buildApiUrl } from "./config";
import {
  cacheShelfCover,
  enforceCacheBudget,
  getCachedFullBook,
  getCachedShelfCover,
  hasCachedShelfCover,
  loadShelfMetadataSync,
  saveFullBookPackage,
  saveShelfMetadata,
} from "./cache/libraryCache";

const COVER_DOWNLOAD_CONCURRENCY = 3;
const INITIAL_VISIBLE_BOOK_COUNT = 6;

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

const App = () => {
  const [theme, setTheme] = useState("");
  const [book, setBook] = useState(null);
  const [loading, setLoading] = useState(false);
  const [, setExistingBookLoading] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [libraryBooks, setLibraryBooks] = useState([]);
  const [libraryLoading, setLibraryLoading] = useState(false);
  const [libraryError, setLibraryError] = useState(false);
  const [visibleBookIds, setVisibleBookIds] = useState([]);
  const [coverStateByBookId, setCoverStateByBookId] = useState({});
  const libraryFetchPromiseRef = useRef(null);
  const cachedCoverUrlsRef = useRef({});
  const cachedBookObjectUrlsRef = useRef([]);
  const coverStateByBookIdRef = useRef({});
  const coverQueueRef = useRef([]);
  const queuedCoverBookIdsRef = useRef(new Set());
  const pendingCoverBookIdsRef = useRef(new Set());
  const inFlightBookSelectionRef = useRef(new Map());

  const updateCoverState = ({ bookId, status, sourceUrl }) => {
    setCoverStateByBookId((currentState) => {
      const previousState = currentState[bookId] ?? {};
      const previousUrl = previousState.url;

      if (previousUrl && previousUrl !== sourceUrl && previousUrl.startsWith("blob:")) {
        URL.revokeObjectURL(previousUrl);
      }

      cachedCoverUrlsRef.current[bookId] = sourceUrl ?? null;

      const nextState = {
        ...currentState,
        [bookId]: {
          status,
          url: sourceUrl ?? null,
        },
      };

      coverStateByBookIdRef.current = nextState;
      return nextState;
    });
  };

  const markCoverStatus = (bookId, status) => {
    setCoverStateByBookId((currentState) => {
      const nextState = {
        ...currentState,
        [bookId]: {
          ...(currentState[bookId] ?? {}),
          status,
        },
      };

      coverStateByBookIdRef.current = nextState;
      return nextState;
    });
  };

  const cacheFullBookInBackground = async (completeBookData) => {
    try {
      await saveFullBookPackage(completeBookData);
      await enforceCacheBudget();
    } catch (error) {
      console.warn("Failed to cache full book package:", error);
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

      const normalizedBook = {
        book_id: bookData.book_id,
        book_title: bookData.book_title,
        json_url: bookData.json_url,
        cover_url: bookData.cover?.url ?? bookData.cover_url ?? null,
        images: bookData.images ?? [],
        ...bookData,
      };

      if (existingIndex >= 0) {
        const nextBooks = [...previousBooks];
        nextBooks[existingIndex] = { ...nextBooks[existingIndex], ...normalizedBook };
        return nextBooks;
      }

      return [normalizedBook, ...previousBooks];
    });
  };

  const fetchLibraryBooks = async ({ force = false } = {}) => {
    if (libraryFetchPromiseRef.current && !force) {
      return libraryFetchPromiseRef.current;
    }

    const fetchPromise = (async () => {
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
        const normalizedBooks = Array.isArray(books) ? books : [];
        setLibraryBooks(normalizedBooks);
        await saveShelfMetadata(normalizedBooks);
      } catch (error) {
        console.error("Failed to prefetch library books:", error);
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
  };

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
      cover_url: data.cover?.url ?? data.cover_url ?? null,
      images: data.images ?? bookData.images ?? [],
    };
  };

  const pumpCoverQueue = async () => {
    if (pendingCoverBookIdsRef.current.size >= COVER_DOWNLOAD_CONCURRENCY) {
      return;
    }

    while (
      pendingCoverBookIdsRef.current.size < COVER_DOWNLOAD_CONCURRENCY &&
      coverQueueRef.current.length > 0
    ) {
      const nextTask = coverQueueRef.current.shift();
      if (!nextTask?.bookId || !nextTask?.coverUrl) {
        continue;
      }

      pendingCoverBookIdsRef.current.add(nextTask.bookId);
      queuedCoverBookIdsRef.current.delete(nextTask.bookId);
      markCoverStatus(nextTask.bookId, "pending");

      cacheShelfCover({
        bookId: nextTask.bookId,
        sourceUrl: nextTask.coverUrl,
      })
        .then(async (objectUrl) => {
          updateCoverState({
            bookId: nextTask.bookId,
            status: "cached",
            sourceUrl: objectUrl,
          });
          await enforceCacheBudget();
        })
        .catch((error) => {
          console.warn(`Failed to cache cover for ${nextTask.bookId}:`, error);
          markCoverStatus(nextTask.bookId, "failed");
        })
        .finally(() => {
          pendingCoverBookIdsRef.current.delete(nextTask.bookId);
          void pumpCoverQueue();
        });
    }
  };

  useEffect(() => {
    const cachedMetadata = loadShelfMetadataSync();
    if (cachedMetadata?.books?.length) {
      setLibraryBooks(cachedMetadata.books);
    }

    fetchLibraryBooks();
  }, []);

  useEffect(() => {
    void saveShelfMetadata(libraryBooks);
  }, [libraryBooks]);

  useEffect(() => {
    if (libraryBooks.length === 0) {
      return;
    }

    const visibleSet = new Set(
      visibleBookIds.length > 0
        ? visibleBookIds
        : libraryBooks.slice(0, INITIAL_VISIBLE_BOOK_COUNT).map((entry) => entry.book_id),
    );

    const visibleBooks = [];
    const nearViewportBooks = [];
    const visibleIndexes = [];

    libraryBooks.forEach((bookEntry, index) => {
      if (visibleSet.has(bookEntry.book_id)) {
        visibleBooks.push(bookEntry);
        visibleIndexes.push(index);
        return;
      }
    });

    const nearestVisibleIndex =
      visibleIndexes.length > 0 ? Math.min(...visibleIndexes) : 0;
    const furthestVisibleIndex =
      visibleIndexes.length > 0 ? Math.max(...visibleIndexes) : INITIAL_VISIBLE_BOOK_COUNT - 1;

    libraryBooks.forEach((bookEntry, index) => {
      if (visibleSet.has(bookEntry.book_id)) {
        return;
      }

      if (
        index >= Math.max(0, nearestVisibleIndex - 4) &&
        index <= Math.min(libraryBooks.length - 1, furthestVisibleIndex + 4)
      ) {
        nearViewportBooks.push(bookEntry);
      }
    });

    const hydrateAndQueueCovers = async () => {
      await Promise.all(
        visibleBooks.map(async (bookEntry) => {
          if (!bookEntry?.book_id || !bookEntry.cover_url) {
            return;
          }

          if (coverStateByBookIdRef.current[bookEntry.book_id]?.status === "cached") {
            return;
          }

          try {
            const cachedCoverUrl = await getCachedShelfCover(bookEntry.book_id, bookEntry.cover_url);
            if (cachedCoverUrl) {
              updateCoverState({
                bookId: bookEntry.book_id,
                status: "cached",
                sourceUrl: cachedCoverUrl,
              });
              return;
            }

            markCoverStatus(bookEntry.book_id, "uncached");
          } catch (error) {
            console.warn(`Failed to hydrate cached cover for ${bookEntry.book_id}:`, error);
            markCoverStatus(bookEntry.book_id, "failed");
          }
        }),
      );

      const candidates = [];
      for (const bookEntry of [...visibleBooks, ...nearViewportBooks]) {
        if (!bookEntry?.book_id || !bookEntry.cover_url) {
          continue;
        }

        const existingState = coverStateByBookIdRef.current[bookEntry.book_id];
        if (existingState?.status === "cached" || existingState?.status === "pending") {
          continue;
        }

        if (queuedCoverBookIdsRef.current.has(bookEntry.book_id)) {
          continue;
        }

        const cached = await hasCachedShelfCover(bookEntry.book_id, bookEntry.cover_url);
        if (cached) {
          continue;
        }

        queuedCoverBookIdsRef.current.add(bookEntry.book_id);
        candidates.push({
          bookId: bookEntry.book_id,
          coverUrl: bookEntry.cover_url,
        });
      }

      if (candidates.length === 0) {
        return;
      }

      coverQueueRef.current = [...candidates, ...coverQueueRef.current];
      void pumpCoverQueue();
    };

    void hydrateAndQueueCovers();
    // The queue runner is ref-driven and should not retrigger this effect.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [libraryBooks, visibleBookIds]);

  const releaseAllCachedObjectUrls = () => {
    releaseObjectUrls(Object.values(cachedCoverUrlsRef.current).filter(Boolean));
    releaseObjectUrls(cachedBookObjectUrlsRef.current);
  };

  useEffect(() => {
    return () => {
      releaseAllCachedObjectUrls();
    };
  }, []);

  const hydratedLibraryBooks = useMemo(
    () =>
      libraryBooks.map((bookEntry) => {
        const coverState = coverStateByBookId[bookEntry.book_id];

        return {
          ...bookEntry,
          render_cover_url: coverState?.url ?? null,
          cover_cache_status: coverState?.status ?? (bookEntry.cover_url ? "uncached" : "missing"),
        };
      }),
    [libraryBooks, coverStateByBookId],
  );

  const openBook = (nextBook) => {
    releaseObjectUrls(cachedBookObjectUrlsRef.current);
    cachedBookObjectUrlsRef.current = nextBook?.__cachedObjectUrls ?? [];
    setBook(nextBook);
    setIsModalOpen(true);
  };

  const handleGenerateBook = async () => {
    if (!theme.trim()) {
      alert("Please enter a theme to generate a book.");
      return;
    }

    setLoading(true);
    setBook(null);

    try {
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
      const completeBookData = {
        ...data,
        ...bookData,
        cover_url: data.cover?.url ?? data.cover_url ?? null,
      };

      openBook(completeBookData);
      upsertBookInLibrary(completeBookData);
      void cacheFullBookInBackground(completeBookData);
    } catch (error) {
      console.error(error);
      setBook(null);
      alert("Error generating book. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleCloseModal = () => {
    releaseObjectUrls(cachedBookObjectUrlsRef.current);
    cachedBookObjectUrlsRef.current = [];
    setIsModalOpen(false);
    setBook(null);
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
        const cachedBook = await getCachedFullBook(bookId);
        if (cachedBook) {
          openBook(cachedBook);
          return;
        }

        const completeBookData = await fetchAndBuildFullBook(bookId);
        openBook(completeBookData);
        upsertBookInLibrary(completeBookData);
        void cacheFullBookInBackground(completeBookData);
      } catch (error) {
        console.error(
          `App.js::handleSelectBook(): Failed to get book ID ${bookId} with error`,
          error,
        );
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
        books={hydratedLibraryBooks}
        loading={libraryLoading && libraryBooks.length === 0}
        error={libraryError && libraryBooks.length === 0}
        onRetry={() => fetchLibraryBooks({ force: true })}
        onSelectBook={handleSelectBook}
        onVisibleBooksChange={setVisibleBookIds}
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
