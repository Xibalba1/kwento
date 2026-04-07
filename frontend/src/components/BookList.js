// kwento/frontend/src/components/BookList.js

import React, { useEffect, useLayoutEffect, useRef, useState } from "react";
import { getImageDebugPageContext, logImageEvent } from "../debug/imageDebug";

const BOOK_SHELF_TAB = "bookshelf";
const FAVORITES_TAB = "favorites";
const ARCHIVE_TAB = "archive";
const TAB_WIDTH = 152;
const TAB_BAR_SIDE_PADDING = 18;
const TAB_HEIGHT = 52;
const TAB_BAR_OVERLAP = 8;
const ACTIVE_TAB_BRIDGE_HEIGHT = 12;
const TAB_OVERLAP = 10;
const MOBILE_TAB_WIDTH = "calc(33.333333% - 5.333333px)";
const MOBILE_TAB_FONT_SIZE = 14;
const MOBILE_TAB_HORIZONTAL_PADDING = 10;
const MOBILE_GRID_MEDIA_QUERY = "(max-width: 600px)";
const CARD_CORNER_RADIUS = 14;

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

const useIsMobileGrid = () => {
  const getPreference = () =>
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia(MOBILE_GRID_MEDIA_QUERY).matches;

  const [isMobileGrid, setIsMobileGrid] = useState(getPreference);

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
      return undefined;
    }

    const mediaQuery = window.matchMedia(MOBILE_GRID_MEDIA_QUERY);
    const handleChange = (event) => {
      setIsMobileGrid(event.matches);
    };

    setIsMobileGrid(mediaQuery.matches);

    if (typeof mediaQuery.addEventListener === "function") {
      mediaQuery.addEventListener("change", handleChange);
      return () => mediaQuery.removeEventListener("change", handleChange);
    }

    mediaQuery.addListener(handleChange);
    return () => mediaQuery.removeListener(handleChange);
  }, []);

  return isMobileGrid;
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
  onUpdateLibraryState = () => {},
  pendingLibraryStateBookIds = [],
}) => {
  const buttonRefs = useRef({});
  const cardInnerRefs = useRef({});
  const itemRefs = useRef({});
  const [layoutVersion, setLayoutVersion] = useState(0);
  const [activeTab, setActiveTab] = useState(BOOK_SHELF_TAB);
  const [flippedBookId, setFlippedBookId] = useState(null);
  const prefersReducedMotion = usePrefersReducedMotion();
  const isMobileGrid = useIsMobileGrid();
  const pendingStateBookIds = new Set(pendingLibraryStateBookIds);
  const visibleBooks = books.filter((book) => {
    if (activeTab === BOOK_SHELF_TAB) {
      return !book.is_archived;
    }

    if (activeTab === FAVORITES_TAB) {
      return Boolean(book.is_favorite) && !book.is_archived;
    }

    return book.is_archived;
  });

  useLayoutEffect(() => {
    if (visibleBooks.length === 0) {
      return;
    }

    const buttonEntries = visibleBooks
      .map((book) => ({
        bookId: book.book_id,
        button: buttonRefs.current[book.book_id] ?? null,
        cardInner: cardInnerRefs.current[book.book_id] ?? null,
      }))
      .filter((entry) => entry.button && entry.cardInner);

    if (buttonEntries.length === 0) {
      return;
    }

    buttonEntries.forEach(({ button, cardInner }) => {
      button.style.height = "auto";
      cardInner.style.height = "auto";
    });

    const measuredEntries = buttonEntries
      .map(({ bookId, button }) => {
        const rect = button.getBoundingClientRect();
        return {
          bookId,
          height: Math.ceil(rect.height),
          top: rect.top,
          left: rect.left,
        };
      })
      .sort((left, right) => {
        if (left.top !== right.top) {
          return left.top - right.top;
        }
        return left.left - right.left;
      });

    const rowTolerance = 4;
    const rows = [];
    measuredEntries.forEach((entry) => {
      const row = rows.find((candidate) => Math.abs(candidate.top - entry.top) <= rowTolerance);
      if (row) {
        row.entries.push(entry);
        row.maxHeight = Math.max(row.maxHeight, entry.height);
        return;
      }

      rows.push({
        top: entry.top,
        maxHeight: entry.height,
        entries: [entry],
      });
    });

    const heightByBookId = rows.reduce((heights, row) => {
      row.entries.forEach((entry) => {
        heights[entry.bookId] = row.maxHeight;
      });
      return heights;
    }, {});

    buttonEntries.forEach(({ bookId, button, cardInner }) => {
      const nextHeight = heightByBookId[bookId];
      if (!nextHeight) {
        return;
      }

      const heightValue = `${nextHeight}px`;
      button.style.height = heightValue;
      cardInner.style.height = heightValue;
    });
  }, [activeTab, books, layoutVersion, visibleBooks]);

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
    onUpdateLibraryState(book.book_id, { is_archived: !book.is_archived });
  };

  const handleFavoriteAction = (event, book) => {
    event.stopPropagation();
    setFlippedBookId(null);
    const isEffectiveFavorite = Boolean(book.is_favorite) && !book.is_archived;
    onUpdateLibraryState(book.book_id, { is_favorite: !isEffectiveFavorite });
  };

  const getTabStyleSet = (tab) => {
    if (tab === FAVORITES_TAB) {
      return {
        tabButton: styles.favoritesTabButton,
        content: styles.favoritesContent,
        bridge: styles.favoritesActiveTabBridge,
        bookButton: styles.favoritesBookButton,
        frontActionButton: styles.favoritesFrontActionButton,
        bookTitle: styles.favoritesBookTitle,
        cardBack: styles.favoritesCardBack,
        backTitle: styles.favoritesBackTitle,
        backActionButton: styles.favoritesBackActionButton,
      };
    }

    if (tab === ARCHIVE_TAB) {
      return {
        tabButton: styles.archiveTabButton,
        content: styles.archiveContent,
        bridge: styles.archiveActiveTabBridge,
        bookButton: styles.archiveBookButton,
        frontActionButton: styles.archiveFrontActionButton,
        bookTitle: styles.archiveBookTitle,
        cardBack: styles.archiveCardBack,
        backTitle: styles.archiveBackTitle,
        backActionButton: styles.archiveBackActionButton,
      };
    }

    return {
      tabButton: null,
      content: null,
      bridge: null,
      bookButton: null,
      frontActionButton: null,
      bookTitle: null,
      cardBack: null,
      backTitle: null,
      backActionButton: null,
    };
  };

  const tabOrder = [BOOK_SHELF_TAB, FAVORITES_TAB, ARCHIVE_TAB];
  const activeTabIndex = Math.max(0, tabOrder.indexOf(activeTab));
  const mobileTabWidth = MOBILE_TAB_WIDTH;
  const mobileTabOffset =
    activeTabIndex === 0
      ? `${TAB_BAR_SIDE_PADDING}px`
      : activeTabIndex === 1
        ? "calc(33.333333% + 2.666667px)"
        : "calc(66.666667% - 12.666667px)";
  const tabBarStyle = {
    ...styles.tabBar,
    ...(isMobileGrid ? styles.mobileTabBar : {}),
  };
  const tabLabelStyle = {
    ...styles.tabLabel,
    ...(isMobileGrid ? styles.mobileTabLabel : {}),
  };
  const tabButtonStyle = (tab, accentStyles = {}) => ({
    ...styles.tabButton,
    ...(isMobileGrid ? styles.mobileTabButton : {}),
    ...accentStyles,
    ...(tab !== BOOK_SHELF_TAB ? styles.trailingTabButton : {}),
    ...(activeTab !== tab ? styles.inactiveTabButton : {}),
    ...(activeTab === tab ? styles.activeTabButton : {}),
  });
  const activeTabBridgeStyle = {
    ...styles.activeTabBridge,
    ...(getTabStyleSet(activeTab).bridge ?? {}),
    ...(isMobileGrid
      ? {
          width: mobileTabWidth,
          left: mobileTabOffset,
        }
      : {
          left:
            activeTab === BOOK_SHELF_TAB
              ? TAB_BAR_SIDE_PADDING
              : activeTab === FAVORITES_TAB
                ? TAB_BAR_SIDE_PADDING + (TAB_WIDTH - TAB_OVERLAP)
                : TAB_BAR_SIDE_PADDING + ((TAB_WIDTH - TAB_OVERLAP) * 2),
        }),
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
            ...(activeTab === FAVORITES_TAB ? styles.favoritesMessage : {}),
          }}
        >
          {activeTab === ARCHIVE_TAB
            ? "Archive is empty"
            : activeTab === FAVORITES_TAB
              ? "You don't have any Favorites yet."
              : "Book Shelf is empty"}
        </p>
      );
    }

    return (
      <ul
        style={{
          ...styles.list,
          ...(isMobileGrid ? styles.mobileList : {}),
        }}
      >
        {visibleBooks.map((book) => (
          (() => {
            const tabStyleSet = getTabStyleSet(activeTab);
            const isPending = pendingStateBookIds.has(book.book_id);
            const isEffectiveFavorite = Boolean(book.is_favorite) && !book.is_archived;

            return (
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
                ref={(element) => {
                  if (element) {
                    cardInnerRefs.current[book.book_id] = element;
                    return;
                  }

                  delete cardInnerRefs.current[book.book_id];
                }}
                style={{
                  ...styles.cardInner,
                  ...(flippedBookId === book.book_id
                    ? prefersReducedMotion
                      ? styles.cardInnerReducedMotionFlipped
                      : styles.cardInnerFlipped
                    : {}),
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
                      ...(tabStyleSet.bookButton ?? {}),
                    }}
                    onClick={() => {
                      onSelectBook(book.book_id);
                    }}
                  >
                    <span
                      style={{
                        ...styles.bookTitle,
                        ...(tabStyleSet.bookTitle ?? {}),
                      }}
                    >
                      {book.book_title}
                    </span>
                    <div style={styles.coverSlot}>
                      <BookCoverImage
                        bookId={book.book_id}
                        coverUrl={book.cover_url}
                        sourceKind={book.cover_source_kind ?? "remote"}
                        bookTitle={book.book_title}
                        onSizeChange={handleSizeChange}
                      />
                    </div>
                  </button>
                  <button
                    type="button"
                    aria-label={`More actions for ${book.book_title}`}
                    style={{
                      ...styles.frontActionButton,
                      ...(tabStyleSet.frontActionButton ?? {}),
                    }}
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
                    ...(tabStyleSet.cardBack ?? {}),
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
                    style={{
                      ...styles.backActionButton,
                      ...(tabStyleSet.backActionButton ?? {}),
                    }}
                    onClick={(event) => handleFlipToggle(event, book.book_id)}
                  >
                    <span style={styles.materialSymbol}>undo</span>
                  </button>
                  <div style={styles.backContent}>
                    <p
                      style={{
                        ...styles.backTitle,
                        ...(tabStyleSet.backTitle ?? {}),
                      }}
                    >
                      {book.book_title}
                    </p>
                    <div style={styles.backActions}>
                      <button
                        type="button"
                        style={{
                          ...styles.menuActionButton,
                          ...(activeTab === ARCHIVE_TAB ? styles.archiveMenuActionButton : {}),
                        }}
                        disabled={isPending}
                        onClick={(event) => handleArchiveAction(event, book)}
                      >
                        {isPending
                          ? "Saving..."
                          : book.is_archived
                            ? "Restore to Book Shelf"
                            : "Move to Archive"}
                      </button>
                      <button
                        type="button"
                        style={styles.favoritesMenuActionButton}
                        disabled={isPending}
                        onClick={(event) => handleFavoriteAction(event, book)}
                      >
                        {isPending
                          ? "Saving..."
                          : isEffectiveFavorite
                            ? "Remove from Favorites"
                            : "Add to Favorites"}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </li>
            );
          })()
        ))}
      </ul>
    );
  };

  return (
    <div style={styles.section}>
      <div style={tabBarStyle} role="tablist" aria-label="Book list sections">
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === BOOK_SHELF_TAB}
          onClick={() => setActiveTab(BOOK_SHELF_TAB)}
          style={tabButtonStyle(BOOK_SHELF_TAB)}
        >
          <span style={tabLabelStyle}>Book Shelf</span>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === FAVORITES_TAB}
          onClick={() => setActiveTab(FAVORITES_TAB)}
          style={tabButtonStyle(FAVORITES_TAB, styles.favoritesTabButton)}
        >
          <span style={tabLabelStyle}>Favorites</span>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === ARCHIVE_TAB}
          onClick={() => setActiveTab(ARCHIVE_TAB)}
          style={tabButtonStyle(ARCHIVE_TAB, styles.archiveTabButton)}
        >
          <span style={tabLabelStyle}>Archive</span>
        </button>
        <div aria-hidden="true" data-testid="active-tab-bridge" style={activeTabBridgeStyle} />
      </div>
      <div
        style={{
          ...styles.content,
          ...(getTabStyleSet(activeTab).content ?? {}),
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
    boxSizing: "border-box",
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
    whiteSpace: "nowrap",
  },
  trailingTabButton: {
    marginLeft: `-${TAB_OVERLAP}px`,
  },
  mobileTabButton: {
    flex: "1 1 0",
    minWidth: "0",
    padding: `0 ${MOBILE_TAB_HORIZONTAL_PADDING}px`,
  },
  mobileTabLabel: {
    fontSize: `${MOBILE_TAB_FONT_SIZE}px`,
  },
  archiveTabButton: {
    backgroundColor: "#FFCC00",
    color: "#CA054D",
  },
  favoritesTabButton: {
    backgroundColor: "#36839b",
    color: "#FFCC00",
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
  favoritesActiveTabBridge: {
    backgroundColor: "#36839b",
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
  favoritesContent: {
    backgroundColor: "#36839b",
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
  mobileList: {
    gridTemplateColumns: "1fr",
  },
  listItem: {
    display: "flex",
  },
  card: {
    position: "relative",
    width: "100%",
    perspective: "1200px",
    borderRadius: `${CARD_CORNER_RADIUS}px`,
    overflow: "hidden",
  },
  cardReducedMotion: {
    perspective: "none",
  },
  cardInner: {
    position: "relative",
    width: "100%",
    transformStyle: "preserve-3d",
    transition: "transform 320ms cubic-bezier(0.22, 1, 0.36, 1)",
    borderRadius: `${CARD_CORNER_RADIUS}px`,
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
    borderRadius: `${CARD_CORNER_RADIUS}px`,
    overflow: "hidden",
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
    padding: "16px 16px 24px 24px",
    backgroundColor: "#FFCC00",
    border: "none",
    borderRadius: `${CARD_CORNER_RADIUS}px`,
    cursor: "pointer",
    transition: "background-color 0.2s",
    textAlign: "center",
    boxShadow: "rgba(0, 0, 0, 0.15) 1.95px 1.95px 2.6px",
    gap: "8px",
    position: "relative",
    outline: "none",
  },
  archiveBookButton: {
    backgroundColor: "#36839b",
  },
  favoritesBookButton: {
    backgroundColor: "#CA054D",
  },
  frontActionButton: {
    position: "absolute",
    bottom: "10px",
    left: "10px",
    width: "42px",
    height: "42px",
    border: "none",
    borderRadius: "999px",
    backgroundColor: "rgba(202, 5, 77, 0.24)",
    color: "#FFFCF0",
    backdropFilter: "blur(4px)",
    WebkitBackdropFilter: "blur(4px)",
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 2,
  },
  archiveFrontActionButton: {
    backgroundColor: "rgba(255, 204, 0, 0.2)",
    color: "#FFCC00",
  },
  favoritesFrontActionButton: {
    backgroundColor: "rgba(255, 204, 0, 0.2)",
    color: "#FFCC00",
  },
  bookTitle: {
    fontSize: "20px",
    color: "#CA054D",
    wordBreak: "break-word",
    overflowWrap: "break-word",
    width: '100%',
    flexShrink: 0,
  },
  archiveBookTitle: {
    color: "#FFCC00",
  },
  favoritesBookTitle: {
    color: "#FFCC00",
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
  archiveCardBack: {
    background: "linear-gradient(160deg, rgba(125, 182, 199, 0.98), rgba(82, 156, 179, 0.98))",
  },
  favoritesCardBack: {
    background: "linear-gradient(160deg, rgba(234, 122, 160, 0.98), rgba(214, 78, 126, 0.98))",
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
  backActions: {
    display: "flex",
    flexDirection: "column",
    gap: "12px",
    width: "100%",
    alignItems: "center",
  },
  backTitle: {
    margin: 0,
    color: "#8A0033",
    fontSize: "16px",
    fontWeight: "600",
    textAlign: "center",
  },
  archiveBackTitle: {
    color: "#FFCC00",
  },
  favoritesBackTitle: {
    color: "#FFCC00",
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
  archiveBackActionButton: {
    backgroundColor: "#FFCC00",
    color: "#CA054D",
  },
  favoritesBackActionButton: {
    backgroundColor: "#FFCC00",
    color: "#36839b",
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
  archiveMenuActionButton: {
    backgroundColor: "#FFCC00",
    color: "#CA054D",
  },
  favoritesMenuActionButton: {
    width: "100%",
    maxWidth: "220px",
    border: "none",
    borderRadius: "14px",
    padding: "14px 18px",
    backgroundColor: "#36839b",
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
  favoritesMessage: {
    color: "#FFCC00",
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
