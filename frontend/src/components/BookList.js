// kwento/frontend/src/components/BookList.js

import React from 'react';

const BookList = ({ books, loading, error, onRetry, onSelectBook, onClose }) => {

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
          <button type="button" style={styles.retryButton} onClick={onRetry}>
            Retry
          </button>
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
    alignItems: "center", // Keep modal centered vertically
    zIndex: 1000, // Ensure the modal is on top
    padding: "20px",
    // Removed overflowY from overlay
  },
  modal: {
    position: "relative",
    width: "90%",
    maxWidth: "600px",
    backgroundColor: "#CA054D",
    borderRadius: "10px",
    padding: "30px",
    paddingBottom: "30px", // Extra padding at the bottom
    boxShadow:"rgba(0, 0, 0, 0.25) 0px 54px 55px, rgba(0, 0, 0, 0.12) 0px -12px 30px, rgba(0, 0, 0, 0.12) 0px 4px 6px, rgba(0, 0, 0, 0.17) 0px 12px 13px, rgba(0, 0, 0, 0.09) 0px -3px 5px",
    display: "flex",
    flexDirection: "column",
    maxHeight: "90vh", // Re-added maxHeight to constrain modal height
    overflowY: "auto", // Enable internal scrolling if content overflows
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
    color: "#FFCC00",
  },
  list: {
    display: 'grid',
    gridTemplateColumns: 'repeat(2, 1fr)',
    gap: '15px',
    listStyleType: 'none',
    padding: 0,
    margin: 0,
  },
  listItem: {
    // No additional styles needed
  },
  bookButton: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flexDirection: 'column',
    width: "100%",
    minHeight: '120px',
    padding: "25px",
    backgroundColor: "#FFCC00",
    border: "none",
    borderRadius: "8px",
    cursor: "pointer",
    transition: "background-color 0.2s",
    textAlign: "center",
    boxShadow: "rgba(0, 0, 0, 0.15) 1.95px 1.95px 2.6px",
  },
  bookTitle: {
    fontSize: "20px",
    color: "#CA054D",
    wordBreak: "break-word",
    overflowWrap: "break-word",
    width: '100%',
  },
  message: {
    textAlign: "center",
    fontSize: "18px",
    color: "#555",
  },
  retryButton: {
    alignSelf: "center",
    marginTop: "12px",
    padding: "8px 16px",
    border: "none",
    borderRadius: "6px",
    backgroundColor: "#FFCC00",
    color: "#CA054D",
    cursor: "pointer",
    fontWeight: "600",
  },
};

export default BookList;
