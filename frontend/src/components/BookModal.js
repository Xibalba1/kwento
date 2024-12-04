// kwento/frontend/src/components/BookModal.js

import React, { useState, useEffect } from "react";

const BookModal = ({ book, onClose, onBackToLibrary }) => {
  const [currentPage, setCurrentPage] = useState(0); // Zero-based index

  // Reset to first page whenever a new book is loaded
  useEffect(() => {
    setCurrentPage(0);
    console.log("BookModal.js: New book loaded. Resetting to first page.");
  }, [book]);

  // Log current page data for debugging
  useEffect(() => {
    if (book && book.pages && book.pages[currentPage]) {
      const page = book.pages[currentPage];
      console.log(
        `BookModal.js::useEffect(): Current Page (${currentPage + 1}):`,
        page
      );
    } else {
      console.log(
        `BookModal.js::useEffect(): No page data available for current page index: ${currentPage}`
      );
    }
  }, [currentPage, book]);

  // Early return if there's no book data
  if (!book || !book.pages || book.pages.length === 0) {
    console.warn("No book data available to display.");
    return null;
  }

  const totalPages = book.pages.length;
  const page = book.pages[currentPage];

  const handleNext = () => {
    if (currentPage < totalPages - 1) {
      setCurrentPage((prev) => prev + 1);
      console.log(
        `BookModal.js::handleNext(): Navigated to next page: ${currentPage + 2}`
      );
    }
  };

  const handlePrev = () => {
    if (currentPage > 0) {
      setCurrentPage((prev) => prev - 1);
      console.log(
        `BookModal.js::handlePrev(): Navigated to previous page: ${currentPage}`
      );
    }
  };

  const handleClose = () => {
    onClose();
    setCurrentPage(0); // Reset to first page when modal is closed
    console.log(
      "BookModal.js::handleClose(): Book modal closed. Resetting current page."
    );
  };

  // Safeguard: Ensure page fields exist
  const textContent =
    page.content?.text_content_of_this_page || "No content available.";
  const currentPageNumber = page.page_number;
  const imageObj = book.images.find((img) => img.page === currentPageNumber);
  const illustrationUrl = imageObj?.url || "";

  console.log(
    `BookModal.js: Page ${currentPage + 1} illustrationUrl:`,
    illustrationUrl
  );
  console.log(
    `BookModal.js: Page ${currentPage + 1} content:`,
    page.content
  );

  console.log("BookModal.js: Rendering Page:", currentPage + 1);
  console.log("BookModal.js: Text Content:", textContent);

  return (
    <div style={styles.overlay}>
      <div style={styles.modal}>
        {/* Back to Library Button */}
        <button
          onClick={onBackToLibrary}
          style={styles.backButton}
          aria-label="Back to Library"
        >
          &#8592; Library {/* Left arrow and text */}
        </button>

        {/* Close Button */}
        <button
          onClick={handleClose}
          style={styles.closeButton}
          aria-label="Close Modal"
        >
          &#10005; {/* Unicode for "X" */}
        </button>

        {/* Book Title */}
        <h2 style={styles.title}>{book.book_title}</h2>

        {/* Image Display */}
        {illustrationUrl ? (
          <img
            src={illustrationUrl}
            alt={`Illustration for page ${currentPageNumber}`}
            style={styles.image}
            onError={(e) => {
              console.error(
                `Failed to load image for page ${currentPageNumber}`,
                e
              );
              e.target.onerror = null; // Prevent infinite loop if fallback also fails
              e.target.src = "";
            }}
          />
        ) : (
          <div style={styles.noImage}>No Image Available</div>
        )}

        {/* Text Content */}
        {textContent ? (
          <p style={styles.textContent}>{textContent}</p>
        ) : (
          <p style={styles.textContent}>No content available.</p>
        )}

        {/* Navigation Arrows */}
        <div style={styles.navigation}>
          {/* Left Arrow */}
          <button
            onClick={handlePrev}
            disabled={currentPage === 0}
            style={{
              ...styles.navButton,
              visibility: currentPage === 0 ? "hidden" : "visible",
            }}
            aria-label="Previous Page"
          >
            &#8592; {/* Unicode for left arrow */}
          </button>

          {/* Right Arrow */}
          <button
            onClick={handleNext}
            disabled={currentPage === totalPages - 1}
            style={{
              ...styles.navButton,
              visibility:
                currentPage === totalPages - 1 ? "hidden" : "visible",
            }}
            aria-label="Next Page"
          >
            &#8594; {/* Unicode for right arrow */}
          </button>
        </div>

        {/* Page Indicator */}
        <div style={styles.pageIndicator}>
          Page {currentPage + 1} of {totalPages}
        </div>
      </div>
    </div>
  );
};

// Inline styles for simplicity
const styles = {
  overlay: {
    position: "fixed",
    top: 0,
    left: 0,
    width: "100vw",
    height: "100vh",
    backgroundColor: "rgba(0, 0, 0, 0.5)", // Semi-transparent background
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    zIndex: 1000, // Ensure the modal is on top
  },
  modal: {
    position: "relative",
    width: "90vw",
    height: "90vh",
    backgroundColor: "#fff",
    boxShadow: "0 4px 8px rgba(0, 0, 0, 0.2)",
    borderRadius: "8px",
    padding: "20px",
    display: "flex",
    flexDirection: "column",
    justifyContent: "space-between",
    overflow: "hidden",
  },
  closeButton: {
    position: "absolute",
    top: "10px",
    right: "10px",
    background: "transparent",
    border: "none",
    fontSize: "24px",
    cursor: "pointer",
    opacity: 0.6,
    transition: "opacity 0.2s",
  },
  title: {
    margin: "0",
    fontSize: "18px",
    textAlign: "center",
  },
  image: {
    maxWidth: "100%",
    maxHeight: "80%",
    objectFit: "contain",
    marginTop: "10px",
    marginBottom: "10px",
  },
  noImage: {
    flexGrow: 1,
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    color: "#888",
    fontStyle: "italic",
    marginTop: "10px",
    marginBottom: "10px",
  },
  textContent: {
    fontSize: "20px",
    textAlign: "center",
    margin: "10px 0",
    flexGrow: 0,
  },
  navigation: {
    position: "absolute",
    top: "50%",
    left: "0",
    right: "0",
    transform: "translateY(-50%)",
    display: "flex",
    justifyContent: "space-between",
    pointerEvents: "none", // Allow buttons to receive pointer events
  },
  navButton: {
    background: "rgba(255, 255, 255, 0.8)",
    border: "none",
    fontSize: "30px",
    cursor: "pointer",
    padding: "10px",
    borderRadius: "50%",
    boxShadow: "0 2px 4px rgba(0, 0, 0, 0.2)",
    pointerEvents: "auto", // Enable pointer events on buttons
    transition: "background 0.2s",
  },
  pageIndicator: {
    textAlign: "center",
    fontSize: "14px",
    color: "#555",
    marginTop: "10px",
  },
  backButton: {
    position: "absolute",
    top: "10px",
    left: "10px",
    background: "transparent",
    border: "none",
    fontSize: "18px",
    cursor: "pointer",
    opacity: 0.6,
    transition: "opacity 0.2s",
  },
};

export default BookModal;
