import React, { useEffect, useRef, useState } from "react";
import ThemeInput from "./components/ThemeInput";
import BookModal from "./components/BookModal";
import BookList from "./components/BookList";
import { buildApiUrl } from "./config";
import {
  enforceCacheBudget,
  getCachedFullBook,
  loadShelfMetadataSync,
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

const App = () => {
  const [theme, setTheme] = useState("");
  const [book, setBook] = useState(null);
  const [loading, setLoading] = useState(false);
  const [, setExistingBookLoading] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [libraryBooks, setLibraryBooks] = useState([]);
  const [libraryLoading, setLibraryLoading] = useState(false);
  const [libraryError, setLibraryError] = useState(false);
  const [, setVisibleBookIds] = useState([]);
  const libraryFetchPromiseRef = useRef(null);
  const cachedBookObjectUrlsRef = useRef([]);
  const previousBookObjectUrlsRef = useRef([]);
  const inFlightBookSelectionRef = useRef(new Map());

  const cacheFullBookInBackground = async (completeBookData) => {
    try {
      await saveFullBookPackage(completeBookData);
      await enforceCacheBudget();
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
        const normalizedBooks = Array.isArray(books) ? books : [];
        setLibraryBooks(normalizedBooks);
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

  useEffect(() => {
    logImageEvent("app:mount", getImageDebugPageContext());
    const cachedMetadata = loadShelfMetadataSync();
    if (cachedMetadata?.books?.length) {
      setLibraryBooks(cachedMetadata.books);
      logImageEvent("shelf:metadata_hydrated", {
        count: cachedMetadata.books.length,
      });
    }

    fetchLibraryBooks();
  }, []);

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
    };
  }, []);

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
          logImageEvent("full_book:cache_hit", {
            book_id: bookId,
          });
          openBook(cachedBook);
          return;
        }

        logImageEvent("full_book:cache_miss", {
          book_id: bookId,
        });
        const completeBookData = await fetchAndBuildFullBook(bookId);
        openBook(completeBookData);
        upsertBookInLibrary(completeBookData);
        void cacheFullBookInBackground(completeBookData);
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
