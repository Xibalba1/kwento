// kwento/frontend/src/App.js

import React, { useState } from "react";
import ThemeInput from "./components/ThemeInput";
import BookModal from "./components/BookModal";

const App = () => {
  const [theme, setTheme] = useState("");
  const [book, setBook] = useState(null);
  const [loading, setLoading] = useState(false);
  const [existingBookLoading, setExistingBookLoading] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false); // State to control BookModal visibility

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
        throw new Error("Failed to generate book");
      }
      const data = await response.json();
      setBook(data);
      setIsModalOpen(true); // Open the BookModal with the new book
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
      setBook(data);
      setIsModalOpen(true); // Open the BookModal with the fetched book
    } catch (error) {
      console.error(error);
      setBook(null);
      alert("Error fetching the book. Please try again.");
    } finally {
      setExistingBookLoading(false);
    }
  };

  return (
    <div style={styles.container}>
      <h1>Kwento - Book Generator</h1>
      <ThemeInput
        theme={theme}
        setTheme={setTheme}
        onSubmit={handleGenerateBook}
        loading={loading}
        onSelectBook={handleSelectBook} // Pass the handler to ThemeInput
      />

      {/* Render the BookModal if a book is selected and modal is open */}
      {isModalOpen && book && <BookModal book={book} onClose={handleCloseModal} />}
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
};

export default App;
