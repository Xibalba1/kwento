// kwento/frontend/src/App.js

import React, { useEffect, useRef, useState } from "react";
import ThemeInput from "./components/ThemeInput";
import BookModal from "./components/BookModal";
import BookList from "./components/BookList";
import { buildApiUrl } from "./config";

const LIBRARY_CACHE_KEY = "kwento_library_books_v1";

const App = () => {
  const [theme, setTheme] = useState("");
  const [book, setBook] = useState(null);
  const [loading, setLoading] = useState(false);
  const [, setExistingBookLoading] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false); // Controls BookModal visibility
  const [isLibraryOpen, setIsLibraryOpen] = useState(false); // Controls BookList visibility
  const [libraryBooks, setLibraryBooks] = useState([]);
  const [libraryLoading, setLibraryLoading] = useState(false);
  const [libraryError, setLibraryError] = useState(false);
  const [libraryHydrated, setLibraryHydrated] = useState(false);
  const libraryFetchPromiseRef = useRef(null);

  const upsertBookInLibrary = (bookData) => {
    if (!bookData || !bookData.book_id) {
      return;
    }

    setLibraryBooks((previousBooks) => {
      const existingIndex = previousBooks.findIndex(
        (existingBook) => existingBook.book_id === bookData.book_id,
      );
      if (existingIndex >= 0) {
        const nextBooks = [...previousBooks];
        nextBooks[existingIndex] = { ...nextBooks[existingIndex], ...bookData };
        return nextBooks;
      }

      return [
        {
          book_id: bookData.book_id,
          book_title: bookData.book_title,
          ...bookData,
        },
        ...previousBooks,
      ];
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
        setLibraryBooks(Array.isArray(books) ? books : []);
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

  useEffect(() => {
    // Hydrate from cache immediately to avoid blank library on first open.
    try {
      const cachedLibraryRaw = localStorage.getItem(LIBRARY_CACHE_KEY);
      if (cachedLibraryRaw) {
        const parsed = JSON.parse(cachedLibraryRaw);
        if (Array.isArray(parsed)) {
          setLibraryBooks(parsed);
        }
      }
    } catch (error) {
      console.warn("Failed to hydrate cached library books:", error);
    } finally {
      setLibraryHydrated(true);
    }

    // Always refresh in background; this does not block UI interactions.
    fetchLibraryBooks();
  }, []);

  useEffect(() => {
    if (!libraryHydrated) {
      return;
    }

    try {
      localStorage.setItem(LIBRARY_CACHE_KEY, JSON.stringify(libraryBooks));
    } catch (error) {
      console.warn("Failed to persist cached library books:", error);
    }
  }, [libraryBooks, libraryHydrated]);

  // Handler to generate a new book based on the theme
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

      // Fetch the complete book data from json_url
      const bookDataResponse = await fetch(data.json_url);
      if (!bookDataResponse.ok) {
        throw new Error("Failed to fetch book data from json_url");
      }
      const bookData = await bookDataResponse.json();

      // Combine the initial data with the fetched book data
      const completeBookData = {
        ...data,
        ...bookData,
      };

      setBook(completeBookData);
      upsertBookInLibrary(completeBookData);
      setIsModalOpen(true);
    } catch (error) {
      console.error(error);
      setBook(null);
      alert("Error generating book. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  // Handler to close the BookModal
  const handleCloseModal = () => {
    setIsModalOpen(false);
    setBook(null); // Reset the book state
  };

  // Handler to open the BookList modal
  const handleOpenLibrary = () => {
    setIsLibraryOpen(true);
  };

  // Handler to close the BookList modal
  const handleCloseLibrary = () => {
    setIsLibraryOpen(false);
  };

  // Handler to fetch a book by ID (triggered from BookList modal)
  const handleSelectBook = async (bookId) => {
    setExistingBookLoading(true);
    setBook(null);

    try {
      const response = await fetch(buildApiUrl(`/books/${bookId}/`), {
        method: "GET",
        headers: { "Content-Type": "application/json" },
      });
      if (!response.ok) {
        throw new Error("Failed to fetch the selected book");
      }
      const data = await response.json();

      // Fetch the complete book data from json_url
      const bookDataResponse = await fetch(data.json_url);
      if (!bookDataResponse.ok) {
        throw new Error("Failed to fetch book data from json_url");
      }
      const bookData = await bookDataResponse.json();

      // Combine the initial data with the fetched book data
      const completeBookData = {
        ...data,
        ...bookData,
      };

      setBook(completeBookData);
      upsertBookInLibrary(completeBookData);
      setIsModalOpen(true);
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
  };

  // Handler to navigate back to the library from BookModal
  const handleBackToLibrary = () => {
    handleCloseModal();
    handleOpenLibrary();
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
        onSelectBook={handleSelectBook}
        onOpenLibrary={handleOpenLibrary}
      />

      {/* Render the BookModal if a book is selected and modal is open */}
      {isModalOpen && book && (
        <BookModal
          book={book}
          onClose={handleCloseModal}
          onBackToLibrary={handleBackToLibrary} // Pass the handler to BookModal
        />
      )}

      {/* Render the BookList modal if it is open */}
      {isLibraryOpen && (
        <BookList
          books={libraryBooks}
          loading={libraryLoading}
          error={libraryError}
          onRetry={() => fetchLibraryBooks({ force: true })}
          onSelectBook={handleSelectBook}
          onClose={handleCloseLibrary}
        />
      )}
    </div>
  );
};

// Inline styles for simplicity
const styles = {
  container: {
    textAlign: "center",
    padding: "20px",
  },
  button: {
    padding: "10px 20px",
    margin: "10px",
    fontSize: "16px",
    color: "#fff",
    border: "none",
    borderRadius: "4px",
  },
  mainTitle: {
    fontSize: "48px",
    margin: "0",
    color: "#ffcc00",
    textShadow: "#FC0 1px 0 1px",
  },
  subTitle: {
    fontSize: "24px",
    margin: "10px 0",
    color: "#ffcc00",
    textShadow: "#FC0 1px 0 1px",
  },
};

export default App;
