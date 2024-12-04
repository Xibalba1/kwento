// kwento/frontend/src/App.js

import React, { useState } from "react";
import ThemeInput from "./components/ThemeInput";
import BookModal from "./components/BookModal";
import BookList from "./components/BookList";

const App = () => {
  const [theme, setTheme] = useState("");
  const [book, setBook] = useState(null);
  const [loading, setLoading] = useState(false);
  const [existingBookLoading, setExistingBookLoading] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false); // Controls BookModal visibility
  const [isLibraryOpen, setIsLibraryOpen] = useState(false); // Controls BookList visibility

  // Handler to generate a new book based on the theme
  const handleGenerateBook = async () => {
    if (!theme.trim()) {
      alert("Please enter a theme to generate a book.");
      return;
    }

    setLoading(true);
    setBook(null);

    try {
      const response = await fetch("http://localhost:8000/books/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ theme }),
      });
      if (!response.ok) {
        const errorData = await response.json();
        alert(errorData.detail || "Error generating book. Please try again.");
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
      setIsModalOpen(true);
    } catch (error) {
      console.error(error);
      setBook(null);
      alert("Error generating book. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  // Handler to fetch a random existing book
  const handleGetRandomBook = async () => {
    setExistingBookLoading(true);
    setBook(null);

    try {
      const response = await fetch("http://localhost:8000/books/random/", {
        method: "GET",
        headers: { "Content-Type": "application/json" },
      });
      if (!response.ok) {
        throw new Error("Failed to fetch an existing book");
      }
      const data = await response.json();
      setBook(data);
      setIsModalOpen(true); // Open the BookModal with the fetched book
    } catch (error) {
      console.error(error);
      console.log(
        `App.js::handleGetRandomBook(): failed to get random book with error ${error}`
      );
      setBook(null);
      alert("Error fetching existing book. Please try again.");
    } finally {
      setExistingBookLoading(false);
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
      const response = await fetch(`http://localhost:8000/books/${bookId}/`, {
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
      setIsModalOpen(true);
    } catch (error) {
      console.error(
        `App.js::handleSelectBook(): Failed to get book ID ${bookId} with error`,
        error
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
      <h2 style={styles.subTitle}>Where every child’s story comes to life.</h2>
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
