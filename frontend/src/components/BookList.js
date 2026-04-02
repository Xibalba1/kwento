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

const usePrefersReducedMotion = () => {
  const getPreference = () =>
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const [prefersReducedMotion, setPrefersReducedMotion] = useState(getPreference);

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
      return undefined;
    }

    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const handleChange = (event) => {
      setPrefersReducedMotion(event.matches);
    };

    setPrefersReducedMotion(mediaQuery.matches);

    if (typeof mediaQuery.addEventListener === "function") {
      mediaQuery.addEventListener("change", handleChange);
      return () => mediaQuery.removeEventListener("change", handleChange);
    }

    mediaQuery.addListener(handleChange);
    return () => mediaQuery.removeListener(handleChange);
  }, []);

  return prefersReducedMotion;
};

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
  onToggleArchive = () => {},
  archiveActionBookIds = [],
}) => {
  const buttonRefs = useRef({});
  const itemRefs = useRef({});
  const [maxButtonHeight, setMaxButtonHeight] = useState(null);
  const [layoutVersion, setLayoutVersion] = useState(0);
  const [activeTab, setActiveTab] = useState(BOOK_SHELF_TAB);
  const [flippedBookId, setFlippedBookId] = useState(null);
  const prefersReducedMotion = usePrefersReducedMotion();
  const pendingArchiveBookIds = new Set(archiveActionBookIds);
  const visibleBooks = books.filter((book) =>
    activeTab === BOOK_SHELF_TAB ? !book.is_archived : book.is_archived,
  );

  useLayoutEffect(() => {
    if (activeTab !== BOOK_SHELF_TAB || visibleBooks.length === 0) {
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
  }, [activeTab, books, layoutVersion, visibleBooks.length]);

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
    setLayoutVersion((currentVersion) => currentVersion + 1);
  }, [activeTab, books.length]);

  useEffect(() => {
    if (!flippedBookId) {
      return undefined;
    }

    const closeOnOutsidePointer = (event) => {
      const container = itemRefs.current[flippedBookId];
      if (!container || container.contains(event.target)) {
        return;
      }
      setFlippedBookId(null);
    };

    document.addEventListener("pointerdown", closeOnOutsidePointer);

    return () => {
      document.removeEventListener("pointerdown", closeOnOutsidePointer);
    };
  }, [flippedBookId]);

  useEffect(() => {
    if (flippedBookId && !visibleBooks.some((book) => book.book_id === flippedBookId)) {
      setFlippedBookId(null);
    }
  }, [flippedBookId, visibleBooks]);

  useEffect(() => {
    if (typeof onVisibleBooksChange !== "function") {
      return undefined;
    }

    if (activeTab !== BOOK_SHELF_TAB || visibleBooks.length === 0) {
      onVisibleBooksChange([]);
      return undefined;
    }

    if (typeof window === "undefined" || typeof window.IntersectionObserver !== "function") {
      onVisibleBooksChange(visibleBooks.slice(0, 6).map((book) => book.book_id));
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

    visibleBooks.forEach((book) => {
      const element = itemRefs.current[book.book_id];
      if (element) {
        observer.observe(element);
      }
    });

    return () => {
      observer.disconnect();
    };
  }, [activeTab, onVisibleBooksChange, visibleBooks]);

  const handleSizeChange = () => {
    setLayoutVersion((currentVersion) => currentVersion + 1);
  };

  const handleFlipToggle = (event, bookId) => {
    event.stopPropagation();
    setFlippedBookId((currentId) => (currentId === bookId ? null : bookId));
  };

  const handleArchiveAction = (event, book) => {
    event.stopPropagation();
    setFlippedBookId(null);
    onToggleArchive(book.book_id, !book.is_archived);
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

    if (visibleBooks.length === 0) {
      return (
        <p
          style={{
            ...styles.message,
            ...(activeTab === ARCHIVE_TAB ? styles.archiveMessage : {}),
          }}
        >
          {activeTab === ARCHIVE_TAB ? "Archive is empty" : "Book Shelf is empty"}
        </p>
      );
    }

    return (
      <ul style={styles.list}>
        {visibleBooks.map((book) => (
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
            <div
              style={{
                ...styles.card,
                ...(prefersReducedMotion ? styles.cardReducedMotion : {}),
              }}
            >
              <div
                style={{
                  ...styles.cardInner,
                  ...(flippedBookId === book.book_id
                    ? prefersReducedMotion
                      ? styles.cardInnerReducedMotionFlipped
                      : styles.cardInnerFlipped
                    : {}),
                  height: maxButtonHeight ? `${maxButtonHeight}px` : "auto",
                }}
              >
                <div
                  style={{
                    ...styles.cardFace,
                    ...styles.cardFront,
                    ...(prefersReducedMotion
                      ? flippedBookId === book.book_id
                        ? styles.hiddenFaceReducedMotion
                        : styles.visibleFaceReducedMotion
                      : {}),
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
                    type="button"
                    aria-label={book.book_title}
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
                  <button
                    type="button"
                    aria-label={`More actions for ${book.book_title}`}
                    style={styles.frontActionButton}
                    onClick={(event) => handleFlipToggle(event, book.book_id)}
                  >
                    <span style={styles.materialSymbol}>more_vert</span>
                  </button>
                </div>
                <div
                  aria-hidden={flippedBookId !== book.book_id}
                  style={{
                    ...styles.cardFace,
                    ...styles.cardBack,
                    ...(prefersReducedMotion ? styles.cardBackReducedMotion : {}),
                    ...(prefersReducedMotion
                      ? flippedBookId === book.book_id
                        ? styles.visibleFaceReducedMotion
                        : styles.hiddenFaceReducedMotion
                      : {}),
                  }}
                >
                  <button
                    type="button"
                    aria-label={`Return to cover for ${book.book_title}`}
                    style={styles.backActionButton}
                    onClick={(event) => handleFlipToggle(event, book.book_id)}
                  >
                    <span style={styles.materialSymbol}>undo</span>
                  </button>
                  <div style={styles.backContent}>
                    <p style={styles.backTitle}>{book.book_title}</p>
                    <button
                      type="button"
                      style={styles.menuActionButton}
                      disabled={pendingArchiveBookIds.has(book.book_id)}
                      onClick={(event) => handleArchiveAction(event, book)}
                    >
                      {pendingArchiveBookIds.has(book.book_id)
                        ? "Saving..."
                        : book.is_archived
                          ? "Restore to Book Shelf"
                          : "Move to Archive"}
                    </button>
                  </div>
                </div>
              </div>
            </div>
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
  card: {
    position: "relative",
    width: "100%",
    perspective: "1200px",
  },
  cardReducedMotion: {
    perspective: "none",
  },
  cardInner: {
    position: "relative",
    width: "100%",
    transformStyle: "preserve-3d",
    transition: "transform 320ms cubic-bezier(0.22, 1, 0.36, 1)",
  },
  cardInnerFlipped: {
    transform: "rotateY(180deg)",
  },
  cardInnerReducedMotionFlipped: {
    transform: "none",
  },
  cardFace: {
    width: "100%",
    boxSizing: "border-box",
    backfaceVisibility: "hidden",
    borderRadius: "14px",
  },
  visibleFaceReducedMotion: {
    opacity: 1,
    visibility: "visible",
    position: "relative",
    transition: "opacity 180ms ease",
  },
  hiddenFaceReducedMotion: {
    opacity: 0,
    visibility: "hidden",
    position: "absolute",
    inset: 0,
    pointerEvents: "none",
    transition: "opacity 180ms ease",
  },
  cardFront: {
    position: "relative",
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
    position: "relative",
    outline: "none",
  },
  frontActionButton: {
    position: "absolute",
    top: "10px",
    right: "10px",
    width: "42px",
    height: "42px",
    border: "none",
    borderRadius: "999px",
    backgroundColor: "rgba(202, 5, 77, 0.3)",
    color: "#FFFCF0",
    backdropFilter: "blur(4px)",
    WebkitBackdropFilter: "blur(4px)",
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 2,
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
  cardBack: {
    position: "absolute",
    inset: 0,
    minHeight: "220px",
    padding: "18px",
    background:
      "linear-gradient(160deg, rgba(255, 244, 196, 0.98), rgba(255, 225, 129, 0.98))",
    boxShadow: "rgba(0, 0, 0, 0.15) 1.95px 1.95px 2.6px",
    transform: "rotateY(180deg)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  cardBackReducedMotion: {
    transform: "none",
  },
  backContent: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "18px",
    width: "100%",
  },
  backTitle: {
    margin: 0,
    color: "#8A0033",
    fontSize: "16px",
    fontWeight: "600",
    textAlign: "center",
  },
  backActionButton: {
    position: "absolute",
    top: "10px",
    right: "10px",
    width: "42px",
    height: "42px",
    border: "none",
    borderRadius: "999px",
    backgroundColor: "#CA054D",
    color: "#FFFCF0",
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  menuActionButton: {
    width: "100%",
    maxWidth: "220px",
    border: "none",
    borderRadius: "14px",
    padding: "14px 18px",
    backgroundColor: "#CA054D",
    color: "#FFCC00",
    fontSize: "15px",
    fontWeight: "700",
    cursor: "pointer",
  },
  materialSymbol: {
    fontFamily: '"Material Symbols Outlined"',
    fontSize: "22px",
    lineHeight: 1,
    fontVariationSettings: '"FILL" 0, "wght" 500, "GRAD" 0, "opsz" 24',
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
