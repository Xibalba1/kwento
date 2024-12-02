// kwento/frontend/src/components/BookList.js

import React, { useEffect, useState } from 'react';

const BookList = ({ onSelectBook, onClose }) => {
  const [books, setBooks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    const fetchBooks = async () => {
      try {
        console.log("Getting books list.")
        const response = await fetch('http://localhost:8000/books/', {
          method: 'GET',
          headers: { 'Content-Type': 'application/json' },
        });
        if (!response.ok) {
          console.log("Book list retrieval failed.")
          throw new Error('Failed to fetch books');
        }
        const data = await response.json();
        setBooks(data);
      } catch (error) {
        console.error(error);
        setError(true);
      } finally {
        setLoading(false);
      }
    };

    fetchBooks();
  }, []);

  if (loading) {
    return (
      <div style={styles.overlay}>
        <div style={styles.modal}>
          <button
            onClick={onClose}
            style={styles.closeButton}
            aria-label="Close Modal"
          >
            &#10005;
          </button>
          <p style={styles.message}>Loading books...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={styles.overlay}>
        <div style={styles.modal}>
          <button
            onClick={onClose}
            style={styles.closeButton}
            aria-label="Close Modal"
          >
            &#10005;
          </button>
          <p style={styles.message}>Error fetching books. Please try again later.</p>
        </div>
      </div>
    );
  }

  return (
    <div style={styles.overlay}>
      <div style={styles.modal}>
        {/* Close Button */}
        <button
          onClick={onClose}
          style={styles.closeButton}
          aria-label="Close Modal"
        >
          &#10005; {/* Unicode for "X" */}
        </button>

        {/* Modal Title */}
        <h2 style={styles.title}>My Library</h2>

        {/* Book List */}
        <ul style={styles.list}>
        {books.map((book) => (
          <li key={book.book_id} style={styles.listItem}>
            <button
              style={styles.bookButton}
              onClick={() => {
                onSelectBook(book.book_id);
                onClose(); // Close the BookList modal after selection
              }}
            >
              <span style={styles.bookIcon} role="img" aria-label="Book">
                📚
              </span>
              <span style={styles.bookTitle}>{book.book_title}</span>
            </button>
          </li>
        ))}
        </ul>
      </div>
    </div>
  );
};

const styles = {
  overlay: {
    position: "fixed",
    top: 0,
    left: 0,
    width: "100vw",
    height: "100vh",
    backgroundColor: "rgba(0, 0, 0, 0.6)", // Semi-transparent background
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    zIndex: 1000, // Ensure the modal is on top
    overflowY: "auto",
    padding: "20px",
  },
  modal: {
    position: "relative",
    width: "90%", // Occupies most vertical area
    maxWidth: "600px", // Adjust as needed for horizontal space
    backgroundColor: "#fff",
    borderRadius: "10px",
    padding: "30px",
    boxShadow: "0 5px 15px rgba(0,0,0,0.3)",
    display: "flex",
    flexDirection: "column",
    maxHeight: "90vh",
  },
  closeButton: {
    position: "absolute",
    top: "15px",
    right: "15px",
    background: "transparent",
    border: "none",
    fontSize: "24px",
    cursor: "pointer",
    color: "#333",
  },
  title: {
    marginBottom: "20px",
    textAlign: "center",
    fontSize: "24px",
    color: "#6200EE",
  },
  list: {
    listStyleType: "none",
    padding: 0,
    margin: 0,
    flexGrow: 1,
    overflowY: "auto",
  },
  listItem: {
    marginBottom: "15px",
  },
  bookButton: {
    display: "flex",
    alignItems: "center",
    width: "100%",
    padding: "10px 15px",
    backgroundColor: "#f5f5f5",
    border: "none",
    borderRadius: "8px",
    cursor: "pointer",
    transition: "background-color 0.2s",
    textAlign: "left",
  },
  bookButtonHover: {
    backgroundColor: "#e0e0e0",
  },
  bookIcon: {
    marginRight: "10px",
    fontSize: "24px",
  },
  bookTitle: {
    fontSize: "18px",
    color: "#333",
    wordBreak: "break-word",
    maxWidth: "80%", // Ensures wrapping for long titles
  },
  message: {
    textAlign: "center",
    fontSize: "18px",
    color: "#555",
  },
};

export default BookList;
