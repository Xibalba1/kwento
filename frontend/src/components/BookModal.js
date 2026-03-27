// kwento/frontend/src/components/BookModal.js

import React, { useEffect, useRef, useState } from "react";

const DEFAULT_ILLUSTRATION_ASPECT_RATIO = "4 / 3";

const buildIllustrationKey = (bookId, pageNumber, illustrationUrl) =>
  `${bookId ?? "unknown-book"}:${pageNumber ?? "unknown-page"}:${illustrationUrl ?? "missing"}`;

const BookModal = ({ book, onClose }) => {
  const [currentPage, setCurrentPage] = useState(0); // Zero-based index
  const [illustrationStatus, setIllustrationStatus] = useState("loading");
  const [illustrationDimensions, setIllustrationDimensions] = useState(null);
  const knownIllustrationDimensionsRef = useRef(new Map());
  const pages = book?.pages ?? [];
  const hasBook = pages.length > 0;
  const totalPages = pages.length;
  const page = hasBook ? pages[currentPage] : null;
  const textContent = page?.content?.text_content_of_this_page || "No content available.";
  const currentPageNumber = page?.page_number;
  const imageObj = book?.images?.find((img) => img.page === currentPageNumber);
  const illustrationUrl = imageObj?.url || "";
  const illustrationKey = buildIllustrationKey(book?.book_id, currentPageNumber, illustrationUrl);

  // Reset to first page whenever a new book is loaded
  useEffect(() => {
    setCurrentPage(0);
  }, [book]);

  const handleNext = () => {
    if (currentPage < totalPages - 1) {
      setCurrentPage((prev) => prev + 1);
    }
  };

  const handlePrev = () => {
    if (currentPage > 0) {
      setCurrentPage((prev) => prev - 1);
    }
  };

  const handleClose = () => {
    onClose();
    setCurrentPage(0); // Reset to first page when modal is closed
  };

  useEffect(() => {
    const knownDimensions = knownIllustrationDimensionsRef.current.get(illustrationKey) ?? null;
    setIllustrationDimensions(knownDimensions);

    if (!illustrationUrl) {
      setIllustrationStatus("missing");
      console.debug(`[BookModal] No illustration available for page ${currentPageNumber}`);
      return;
    }

    setIllustrationStatus("loading");
    console.debug(`[BookModal] Starting illustration transition for page ${currentPageNumber}`);
  }, [currentPageNumber, illustrationKey, illustrationUrl]);

  // Early return if there's no book data
  if (!hasBook) {
    return null;
  }

  const illustrationFrameStyle = illustrationDimensions
    ? {
        aspectRatio: `${illustrationDimensions.width} / ${illustrationDimensions.height}`,
      }
    : {
        aspectRatio: DEFAULT_ILLUSTRATION_ASPECT_RATIO,
      };

  const showPlaceholder = illustrationStatus !== "loaded";
  const placeholderLabel = `page ${currentPageNumber} illustration`;

  return (
    <div style={styles.overlay}>
      <div style={styles.modal}>
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
        <div style={{ ...styles.illustrationFrame, ...illustrationFrameStyle }}>
          {showPlaceholder && (
            <div
              aria-label={placeholderLabel}
              data-testid="page-illustration-placeholder"
              style={styles.placeholder}
            >
              {placeholderLabel}
            </div>
          )}
          {illustrationUrl && illustrationStatus !== "error" ? (
            <img
              key={illustrationKey}
              src={illustrationUrl}
              alt={`Illustration for page ${currentPageNumber}`}
              style={{
                ...styles.image,
                ...(showPlaceholder ? styles.imageHidden : styles.imageVisible),
              }}
              onLoad={(event) => {
                const nextDimensions = {
                  width: event.currentTarget.naturalWidth || 0,
                  height: event.currentTarget.naturalHeight || 0,
                };

                if (nextDimensions.width > 0 && nextDimensions.height > 0) {
                  knownIllustrationDimensionsRef.current.set(illustrationKey, nextDimensions);
                  setIllustrationDimensions(nextDimensions);
                }

                setIllustrationStatus("loaded");
                console.debug(`[BookModal] Illustration loaded for page ${currentPageNumber}`);
              }}
              onError={(event) => {
                console.error(`Failed to load image for page ${currentPageNumber}`, event);
                setIllustrationStatus("error");
                event.currentTarget.onerror = null;
              }}
            />
          ) : null}
        </div>

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
    width: "100%",
    height: "100%",
    objectFit: "contain",
  },
  imageHidden: {
    opacity: 0,
    pointerEvents: "none",
  },
  imageVisible: {
    opacity: 1,
  },
  illustrationFrame: {
    flexGrow: 1,
    width: "100%",
    minHeight: "320px",
    marginTop: "10px",
    marginBottom: "10px",
    position: "relative",
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
  },
  placeholder: {
    position: "absolute",
    inset: 0,
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    color: "#888",
    fontStyle: "italic",
    textTransform: "none",
    border: "1px dashed #d0d0d0",
    borderRadius: "8px",
    backgroundColor: "#fafafa",
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
};

export default BookModal;
