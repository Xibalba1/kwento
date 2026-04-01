// kwento/frontend/src/components/BookList.js

import React, { useEffect, useLayoutEffect, useRef, useState } from "react";
import { getImageDebugPageContext, logImageEvent } from "../debug/imageDebug";

const BOOK_SHELF_TAB = "bookshelf";
const ARCHIVE_TAB = "archive";
const TAB_WIDTH = 152;
const TAB_BAR_SIDE_PADDING = 18;
const TAB_HEIGHT = 52;
const TAB_BAR_OVERLAP = 8;
const ACTIVE_TAB_BRIDGE_HEIGHT = 12;

const BookCoverImage = ({ bookId, coverUrl, sourceKind, bookTitle, onSizeChange }) => {
  const [isVisible, setIsVisible] = useState(Boolean(coverUrl));
  const imageRef = useRef(null);

  const buildImageSnapshot = () => {
    const image = imageRef.current;
    if (!image) {
      return null;
    }

    const rect = image.getBoundingClientRect();
    return {
      current_src: image.currentSrc || image.src || null,
      complete: image.complete,
      natural_width: image.naturalWidth,
      natural_height: image.naturalHeight,
      client_width: image.clientWidth,
      client_height: image.clientHeight,
      rect_width: Math.round(rect.width),
      rect_height: Math.round(rect.height),
    };
  };

  useEffect(() => {
    setIsVisible(Boolean(coverUrl));
    logImageEvent("img:prop_change", {
      book_id: bookId,
      render_cover_url: coverUrl,
      source_kind: sourceKind,
      is_visible: Boolean(coverUrl),
    });
  }, [bookId, coverUrl, sourceKind]);

  useEffect(() => {
    logImageEvent("img:component_mount", {
      book_id: bookId,
      render_cover_url: coverUrl,
      source_kind: sourceKind,
    });

    return () => {
      logImageEvent("img:component_unmount", {
        book_id: bookId,
        render_cover_url: coverUrl,
        source_kind: sourceKind,
      });
    };
  }, [bookId, coverUrl, sourceKind]);

  if (!coverUrl || !isVisible) {
    return null;
  }

  return (
    <div style={styles.coverFrame}>
      <img
        ref={imageRef}
        src={coverUrl}
        alt={`Cover for ${bookTitle}`}
        style={styles.coverImage}
        onLoad={() => {
          logImageEvent("img:load", {
            book_id: bookId,
            render_cover_url: coverUrl,
            source_kind: sourceKind,
            snapshot: buildImageSnapshot(),
          });
          onSizeChange();
        }}
        onError={() => {
          logImageEvent("img:error", {
            book_id: bookId,
            render_cover_url: coverUrl,
            source_kind: sourceKind,
            snapshot: buildImageSnapshot(),
            page: getImageDebugPageContext(),
          });
          setIsVisible(false);
          onSizeChange();
        }}
      />
    </div>
  );
};

const BookList = ({
  books,
  loading,
  error,
  onRetry,
  onSelectBook,
  onVisibleBooksChange,
}) => {
  const buttonRefs = useRef({});
  const itemRefs = useRef({});
  const [maxButtonHeight, setMaxButtonHeight] = useState(null);
  const [layoutVersion, setLayoutVersion] = useState(0);
  const [activeTab, setActiveTab] = useState(BOOK_SHELF_TAB);

  useLayoutEffect(() => {
    if (activeTab !== BOOK_SHELF_TAB || books.length === 0) {
      setMaxButtonHeight(null);
      return;
    }

    const buttons = Object.values(buttonRefs.current).filter(Boolean);
    if (buttons.length === 0) {
      return;
    }

    buttons.forEach((button) => {
      button.style.height = "auto";
    });

    const tallestHeight = Math.ceil(
      Math.max(...buttons.map((button) => button.getBoundingClientRect().height)),
    );

    setMaxButtonHeight((currentHeight) =>
      currentHeight === tallestHeight ? currentHeight : tallestHeight,
    );
  }, [activeTab, books, layoutVersion]);

  useEffect(() => {
    const handleResize = () => {
      setLayoutVersion((currentVersion) => currentVersion + 1);
    };

    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
    };
  }, []);

  useEffect(() => {
    if (typeof onVisibleBooksChange !== "function") {
      return undefined;
    }

    if (activeTab !== BOOK_SHELF_TAB || books.length === 0) {
      onVisibleBooksChange([]);
      return undefined;
    }

    if (typeof window === "undefined" || typeof window.IntersectionObserver !== "function") {
      onVisibleBooksChange(books.slice(0, 6).map((book) => book.book_id));
      return undefined;
    }

    const visibleBookIds = new Set();
    const observer = new window.IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          const { bookId } = entry.target.dataset;
          if (!bookId) {
            return;
          }

          if (entry.isIntersecting) {
            visibleBookIds.add(bookId);
            logImageEvent("viewport:enter", {
              book_id: bookId,
              intersection_ratio: entry.intersectionRatio,
            });
            return;
          }

          visibleBookIds.delete(bookId);
          logImageEvent("viewport:exit", {
            book_id: bookId,
            intersection_ratio: entry.intersectionRatio,
          });
        });

        onVisibleBooksChange(Array.from(visibleBookIds));
      },
      {
        root: null,
        rootMargin: "240px 0px",
        threshold: 0.01,
      },
    );

    books.forEach((book) => {
      const element = itemRefs.current[book.book_id];
      if (element) {
        observer.observe(element);
      }
    });

    return () => {
      observer.disconnect();
    };
  }, [activeTab, books, onVisibleBooksChange]);

  const handleSizeChange = () => {
    setLayoutVersion((currentVersion) => currentVersion + 1);
  };

  const renderContent = () => {
    if (loading) {
      return <p style={styles.message}>Loading books...</p>;
    }

    if (error) {
      return (
        <div style={styles.feedbackPanel}>
          <p style={styles.message}>Error fetching books. Please try again later.</p>
          <button type="button" style={styles.retryButton} onClick={onRetry}>
            Retry
          </button>
        </div>
      );
    }

    if (activeTab === ARCHIVE_TAB) {
      return <p style={{ ...styles.message, ...styles.archiveMessage }}>Archive is empty</p>;
    }

    return (
      <ul style={styles.list}>
        {books.map((book) => (
          <li
            key={book.book_id}
            style={styles.listItem}
            data-book-id={book.book_id}
            ref={(element) => {
              if (element) {
                itemRefs.current[book.book_id] = element;
                return;
              }

              delete itemRefs.current[book.book_id];
            }}
          >
            <button
              ref={(element) => {
                if (element) {
                  buttonRefs.current[book.book_id] = element;
                  return;
                }

                delete buttonRefs.current[book.book_id];
              }}
              style={{
                ...styles.bookButton,
                height: maxButtonHeight ? `${maxButtonHeight}px` : "auto",
              }}
              onClick={() => {
                onSelectBook(book.book_id);
              }}
            >
              <span style={styles.bookTitle}>{book.book_title}</span>
              <div style={styles.coverSlot}>
                <BookCoverImage
                  bookId={book.book_id}
                  coverUrl={book.cover_url}
                  sourceKind="remote"
                  bookTitle={book.book_title}
                  onSizeChange={handleSizeChange}
                />
              </div>
            </button>
          </li>
        ))}
      </ul>
    );
  };

  return (
    <div style={styles.section}>
      <div style={styles.tabBar} role="tablist" aria-label="Book list sections">
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === BOOK_SHELF_TAB}
          onClick={() => setActiveTab(BOOK_SHELF_TAB)}
          style={{
            ...styles.tabButton,
            ...(activeTab !== BOOK_SHELF_TAB ? styles.inactiveTabButton : {}),
            ...(activeTab === BOOK_SHELF_TAB ? styles.activeTabButton : {}),
          }}
        >
          <span style={styles.tabLabel}>Book Shelf</span>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === ARCHIVE_TAB}
          onClick={() => setActiveTab(ARCHIVE_TAB)}
          style={{
            ...styles.tabButton,
            ...styles.archiveTabButton,
            ...styles.trailingTabButton,
            ...(activeTab !== ARCHIVE_TAB ? styles.inactiveTabButton : {}),
            ...(activeTab === ARCHIVE_TAB ? styles.activeTabButton : {}),
          }}
        >
          <span style={styles.tabLabel}>Archive</span>
        </button>
        <div
          aria-hidden="true"
          data-testid="active-tab-bridge"
          style={{
            ...styles.activeTabBridge,
            ...(activeTab === ARCHIVE_TAB ? styles.archiveActiveTabBridge : {}),
            left:
              activeTab === BOOK_SHELF_TAB
                ? TAB_BAR_SIDE_PADDING
                : TAB_BAR_SIDE_PADDING + TAB_WIDTH,
          }}
        />
      </div>
      <div
        style={{
          ...styles.content,
          ...(activeTab === ARCHIVE_TAB ? styles.archiveContent : {}),
        }}
      >
        {renderContent()}
      </div>
    </div>
  );
};

const styles = {
  section: {
    width: "100%",
    maxWidth: "600px",
    margin: "0 auto",
    paddingTop: "18px",
    boxSizing: "border-box",
  },
  tabBar: {
    display: "flex",
    gap: "0",
    alignItems: "flex-end",
    padding: `0 ${TAB_BAR_SIDE_PADDING}px`,
    marginBottom: `-${TAB_BAR_OVERLAP}px`,
    position: "relative",
  },
  tabButton: {
    flex: `0 0 ${TAB_WIDTH}px`,
    minWidth: `${TAB_WIDTH}px`,
    minHeight: `${TAB_HEIGHT}px`,
    height: `${TAB_HEIGHT}px`,
    padding: "0 18px",
    border: "none",
    borderTopLeftRadius: "20px",
    borderTopRightRadius: "20px",
    borderBottomLeftRadius: "0",
    borderBottomRightRadius: "0",
    backgroundColor: "#CA054D",
    color: "#FFCC00",
    cursor: "pointer",
    fontSize: "16px",
    fontWeight: "600",
    lineHeight: 1.1,
    textAlign: "center",
    position: "relative",
    boxSizing: "border-box",
    boxShadow: "none",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    transition: "box-shadow 0.2s ease, transform 0.2s ease, filter 0.2s ease",
  },
  tabLabel: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    minHeight: "100%",
  },
  trailingTabButton: {
    marginLeft: "-10px",
  },
  archiveTabButton: {
    backgroundColor: "#FFCC00",
    color: "#CA054D",
  },
  inactiveTabButton: {
    zIndex: 1,
    filter: "brightness(0.96)",
    boxShadow: "0 -2px 10px rgba(0, 0, 0, 0.08)",
  },
  activeTabButton: {
    zIndex: 4,
    boxShadow: "none",
  },
  activeTabBridge: {
    position: "absolute",
    bottom: `-${TAB_BAR_OVERLAP}px`,
    width: `${TAB_WIDTH}px`,
    height: `${ACTIVE_TAB_BRIDGE_HEIGHT}px`,
    backgroundColor: "#CA054D",
    zIndex: 3,
    pointerEvents: "none",
  },
  archiveActiveTabBridge: {
    backgroundColor: "#FFCC00",
  },
  content: {
    minHeight: "48px",
    backgroundColor: "#CA054D",
    border: "none",
    borderRadius: "18px",
    padding: "26px 30px 30px",
    position: "relative",
    zIndex: 2,
    boxSizing: "border-box",
    boxShadow:
      "0 18px 28px -16px rgba(0, 0, 0, 0.24), 0 10px 16px -12px rgba(0, 0, 0, 0.16)",
  },
  archiveContent: {
    backgroundColor: "#FFCC00",
    color: "#CA054D",
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
    display: "flex",
  },
  bookButton: {
    display: "flex",
    alignItems: "center",
    justifyContent: "flex-start",
    flexDirection: 'column',
    width: "100%",
    minHeight: '220px',
    padding: "16px",
    backgroundColor: "#FFCC00",
    border: "none",
    borderRadius: "8px",
    cursor: "pointer",
    transition: "background-color 0.2s",
    textAlign: "center",
    boxShadow: "rgba(0, 0, 0, 0.15) 1.95px 1.95px 2.6px",
    gap: "8px",
  },
  bookTitle: {
    fontSize: "20px",
    color: "#CA054D",
    wordBreak: "break-word",
    overflowWrap: "break-word",
    width: '100%',
    flexShrink: 0,
  },
  coverSlot: {
    width: "100%",
    flex: 1,
    minHeight: "180px",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  coverFrame: {
    width: "100%",
    maxWidth: "220px",
    aspectRatio: "3 / 4",
    borderRadius: "8px",
    overflow: "hidden",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  coverImage: {
    width: "100%",
    height: "100%",
    display: "block",
    objectFit: "cover",
  },
  message: {
    textAlign: "center",
    fontSize: "18px",
    color: "#FFCC00",
    margin: 0,
  },
  archiveMessage: {
    color: "#CA054D",
  },
  feedbackPanel: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
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
