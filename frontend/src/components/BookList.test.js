import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import BookList from "./BookList";

const createMatchMediaController = () => {
  const listenersByQuery = new Map();
  const mediaQueryListsByQuery = new Map();
  const matchStateByQuery = new Map();

  const ensureQueryState = (query) => {
    if (!listenersByQuery.has(query)) {
      listenersByQuery.set(query, new Set());
    }

    if (!matchStateByQuery.has(query)) {
      matchStateByQuery.set(query, false);
    }
  };

  const notifyListeners = (query, matches) => {
    const listeners = listenersByQuery.get(query) ?? new Set();
    const event = { matches, media: query };

    listeners.forEach((listener) => listener(event));
  };

  const matchMedia = jest.fn((query) => {
    ensureQueryState(query);

    if (mediaQueryListsByQuery.has(query)) {
      return mediaQueryListsByQuery.get(query);
    }

    const mediaQueryList = {
      media: query,
      get matches() {
        return matchStateByQuery.get(query) ?? false;
      },
      onchange: null,
      addEventListener: jest.fn((eventName, listener) => {
        if (eventName === "change") {
          listenersByQuery.get(query).add(listener);
        }
      }),
      removeEventListener: jest.fn((eventName, listener) => {
        if (eventName === "change") {
          listenersByQuery.get(query).delete(listener);
        }
      }),
      addListener: jest.fn((listener) => {
        listenersByQuery.get(query).add(listener);
      }),
      removeListener: jest.fn((listener) => {
        listenersByQuery.get(query).delete(listener);
      }),
      dispatchEvent: jest.fn(),
    };

    mediaQueryListsByQuery.set(query, mediaQueryList);
    return mediaQueryList;
  });

  return {
    matchMedia,
    setMatches(query, matches) {
      ensureQueryState(query);
      matchStateByQuery.set(query, matches);
      notifyListeners(query, matches);
    },
  };
};

const baseProps = {
  loading: false,
  error: false,
  onRetry: jest.fn(),
  onSelectBook: jest.fn(),
  onUpdateLibraryState: jest.fn(),
};

const renderBookList = (books) =>
  render(<BookList {...baseProps} books={books} />);

const exactName = (label) => new RegExp(`^${label}$`, "i");
const mobileGridQuery = "(max-width: 600px)";
let matchMediaController;

const getRenderedBookTitles = () =>
  screen.getAllByRole("listitem").map((item) => item.querySelector('button[aria-label]')?.getAttribute("aria-label"));

describe("BookList", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    matchMediaController = createMatchMediaController();
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      configurable: true,
      value: matchMediaController.matchMedia,
    });
  });

  test("renders the tab bar with Book Shelf active by default", () => {
    renderBookList([
      {
        book_id: "book-1",
        book_title: "Default Shelf Book",
        is_archived: false,
      },
    ]);

    expect(screen.getByRole("tab", { name: /book shelf/i })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: /favorites/i })).toHaveAttribute("aria-selected", "false");
    expect(screen.getByRole("tab", { name: /archive/i })).toHaveAttribute("aria-selected", "false");
    expect(screen.getByRole("button", { name: exactName("Default Shelf Book") })).toBeInTheDocument();
  });

  test("shows title sorting as active by default", () => {
    renderBookList([
      {
        book_id: "book-b",
        book_title: "Bravo",
        is_archived: false,
      },
      {
        book_id: "book-a",
        book_title: "Alpha",
        is_archived: false,
      },
    ]);

    expect(screen.getByRole("button", { name: /title/i })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: /created/i })).toHaveAttribute("aria-pressed", "false");
    expect(getRenderedBookTitles()).toEqual(["Alpha", "Bravo"]);
  });

  test("uses a shared label wrapper and consistent tab height for all tabs", () => {
    renderBookList([
      {
        book_id: "book-shared-label",
        book_title: "Shared Label Book",
        is_archived: false,
      },
    ]);

    const shelfTab = screen.getByRole("tab", { name: /book shelf/i });
    const favoritesTab = screen.getByRole("tab", { name: /favorites/i });
    const archiveTab = screen.getByRole("tab", { name: /archive/i });
    const shelfLabel = shelfTab.querySelector("span");
    const favoritesLabel = favoritesTab.querySelector("span");
    const archiveLabel = archiveTab.querySelector("span");

    expect(shelfLabel.tagName).toBe("SPAN");
    expect(favoritesLabel.tagName).toBe("SPAN");
    expect(archiveLabel.tagName).toBe("SPAN");
    expect(shelfTab).toContainElement(shelfLabel);
    expect(favoritesTab).toContainElement(favoritesLabel);
    expect(archiveTab).toContainElement(archiveLabel);
    expect(shelfTab).toHaveStyle({ display: "flex", alignItems: "center", justifyContent: "center" });
    expect(favoritesTab).toHaveStyle({ display: "flex", alignItems: "center", justifyContent: "center" });
    expect(archiveTab).toHaveStyle({ display: "flex", alignItems: "center", justifyContent: "center" });
    expect(shelfTab.style.width).toBe("");
    expect(shelfTab.style.flex).toBe("0 0 152px");
    expect(favoritesTab.style.flex).toBe("0 0 152px");
    expect(archiveTab.style.flex).toBe("0 0 152px");
    expect(shelfTab.style.height).toBe("52px");
    expect(favoritesTab.style.height).toBe("52px");
    expect(archiveTab.style.height).toBe("52px");
    expect(shelfLabel).toHaveStyle({ minHeight: "100%" });
    expect(favoritesLabel).toHaveStyle({ minHeight: "100%" });
    expect(archiveLabel).toHaveStyle({ minHeight: "100%" });
    expect(shelfLabel).toHaveStyle({ whiteSpace: "nowrap" });
    expect(favoritesLabel).toHaveStyle({ whiteSpace: "nowrap" });
    expect(archiveLabel).toHaveStyle({ whiteSpace: "nowrap" });
  });

  test("keeps a shared active-tab bridge without inactive-only label offsets", () => {
    renderBookList([
      {
        book_id: "book-bridge",
        book_title: "Bridge Book",
        is_archived: false,
      },
    ]);

    const bridge = screen.getByTestId("active-tab-bridge");
    const shelfTab = screen.getByRole("tab", { name: /book shelf/i });
    const favoritesTab = screen.getByRole("tab", { name: /favorites/i });
    const archiveTab = screen.getByRole("tab", { name: /archive/i });

    expect(bridge).toHaveStyle({ bottom: "-8px", height: "12px" });
    expect(bridge.style.width).toBe("152px");
    expect(bridge.style.left).toBe("18px");
    expect(shelfTab.style.transform).toBe("");
    expect(favoritesTab.style.transform).toBe("");
    expect(archiveTab.style.transform).toBe("");
    expect(shelfTab.style.top).toBe("");
    expect(favoritesTab.style.top).toBe("");
    expect(archiveTab.style.top).toBe("");
    expect(shelfTab.querySelector("span")).not.toHaveStyle({ transform: expect.any(String) });
    expect(favoritesTab.querySelector("span")).not.toHaveStyle({ transform: expect.any(String) });
    expect(archiveTab.querySelector("span")).not.toHaveStyle({ transform: expect.any(String) });
  });

  test("uses flexible tab sizing and smaller labels on mobile", () => {
    matchMediaController.setMatches(mobileGridQuery, true);

    renderBookList([
      {
        book_id: "mobile-tab-book",
        book_title: "Mobile Tab Book",
        is_archived: false,
      },
    ]);

    const shelfTab = screen.getByRole("tab", { name: /book shelf/i });
    const favoritesTab = screen.getByRole("tab", { name: /favorites/i });
    const archiveTab = screen.getByRole("tab", { name: /archive/i });
    const shelfLabel = shelfTab.querySelector("span");
    const favoritesLabel = favoritesTab.querySelector("span");
    const archiveLabel = archiveTab.querySelector("span");

    expect(shelfTab.style.flex).toBe("1 1 0px");
    expect(favoritesTab.style.flex).toBe("1 1 0px");
    expect(archiveTab.style.flex).toBe("1 1 0px");
    expect(shelfTab.style.minWidth).toBe("0");
    expect(favoritesTab.style.minWidth).toBe("0");
    expect(archiveTab.style.minWidth).toBe("0");
    expect(shelfTab.style.padding).toBe("0px 10px");
    expect(favoritesTab.style.padding).toBe("0px 10px");
    expect(archiveTab.style.padding).toBe("0px 10px");
    expect(shelfLabel.style.fontSize).toBe("14px");
    expect(favoritesLabel.style.fontSize).toBe("14px");
    expect(archiveLabel.style.fontSize).toBe("14px");
    expect(shelfLabel).toHaveStyle({ whiteSpace: "nowrap" });
    expect(favoritesLabel).toHaveStyle({ whiteSpace: "nowrap" });
    expect(archiveLabel).toHaveStyle({ whiteSpace: "nowrap" });
  });

  test("uses responsive bridge sizing and offsets on mobile", () => {
    matchMediaController.setMatches(mobileGridQuery, true);

    renderBookList([
      {
        book_id: "mobile-bridge-book",
        book_title: "Mobile Bridge Book",
        is_archived: false,
      },
    ]);

    const bridge = screen.getByTestId("active-tab-bridge");
    const tabList = screen.getByRole("tablist", { name: /book list sections/i });

    expect(tabList).toHaveStyle({ boxSizing: "border-box" });
    expect(bridge.style.width).toBe("calc(33.333333% - 5.333333px)");
    expect(bridge.style.left).toBe("18px");

    fireEvent.click(screen.getByRole("tab", { name: /favorites/i }));
    expect(screen.getByRole("tab", { name: /favorites/i })).toHaveAttribute("aria-selected", "true");
    expect(bridge.style.left).toBe("calc(33.333333% + 2.666667px)");

    fireEvent.click(screen.getByRole("tab", { name: /archive/i }));
    expect(screen.getByRole("tab", { name: /archive/i })).toHaveAttribute("aria-selected", "true");
    expect(bridge.style.left).toBe("calc(66.666667% - 12.666667px)");
  });

  test("uses two columns by default on desktop", () => {
    renderBookList([
      {
        book_id: "desktop-grid-book-1",
        book_title: "Desktop Grid Book 1",
        is_archived: false,
      },
      {
        book_id: "desktop-grid-book-2",
        book_title: "Desktop Grid Book 2",
        is_archived: false,
      },
    ]);

    const list = screen.getByRole("list");

    expect(list).toHaveStyle({ gridTemplateColumns: "repeat(2, 1fr)" });
  });

  test("uses one column on mobile", () => {
    matchMediaController.setMatches(mobileGridQuery, true);

    renderBookList([
      {
        book_id: "mobile-grid-book-1",
        book_title: "Mobile Grid Book 1",
        is_archived: false,
      },
      {
        book_id: "mobile-grid-book-2",
        book_title: "Mobile Grid Book 2",
        is_archived: false,
      },
    ]);

    const list = screen.getByRole("list");

    expect(list).toHaveStyle({ gridTemplateColumns: "1fr" });
  });

  test("keeps the sort controls inline on mobile", () => {
    matchMediaController.setMatches(mobileGridQuery, true);

    renderBookList([
      {
        book_id: "mobile-sort-book-1",
        book_title: "Mobile Sort Book 1",
        is_archived: false,
      },
    ]);

    const sortGroup = screen.getByRole("group", { name: /sort books/i });
    expect(sortGroup).toHaveStyle({ display: "flex" });
    expect(screen.getByRole("button", { name: /title/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /created/i })).toBeInTheDocument();
  });

  test("updates the grid when the mobile media query changes", () => {
    renderBookList([
      {
        book_id: "responsive-grid-book-1",
        book_title: "Responsive Grid Book 1",
        is_archived: false,
      },
      {
        book_id: "responsive-grid-book-2",
        book_title: "Responsive Grid Book 2",
        is_archived: false,
      },
    ]);

    const list = screen.getByRole("list");

    expect(list).toHaveStyle({ gridTemplateColumns: "repeat(2, 1fr)" });

    act(() => {
      matchMediaController.setMatches(mobileGridQuery, true);
    });

    expect(list).toHaveStyle({ gridTemplateColumns: "1fr" });
    expect(screen.getByRole("button", { name: exactName("Responsive Grid Book 1") })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: exactName("Responsive Grid Book 2") })).toBeInTheDocument();
  });

  test("renders title and cover image inside the book button when cover_url is present", () => {
    renderBookList([
      {
        book_id: "book-2",
        book_title: "The Cover Book",
        cover_url: "https://example.com/cover.png",
        is_archived: false,
      },
    ]);

    const button = screen.getByRole("button", { name: exactName("The Cover Book") });
    expect(button).toHaveTextContent("The Cover Book");

    const image = screen.getByRole("img", { name: /cover for the cover book/i });
    const frame = image.parentElement;
    expect(image).toBeInTheDocument();
    expect(button).toContainElement(image);
    expect(frame).toHaveStyle("border-radius: 8px");
    expect(frame).toHaveStyle("overflow: hidden");
    expect(frame.style.aspectRatio).toBe("3 / 4");
    expect(image).toHaveStyle({
      width: "100%",
      height: "100%",
      objectFit: "cover",
    });
  });

  test("renders title-only when no shelf cover URL is available", () => {
    renderBookList([
      {
        book_id: "book-3",
        book_title: "Title Only",
        is_archived: false,
      },
    ]);

    const button = screen.getByRole("button", { name: exactName("Title Only") });
    expect(button).toBeInTheDocument();
    expect(button).toHaveStyle({ backgroundColor: "#FFCC00" });
    expect(within(button).getByText("Title Only")).toHaveStyle({ color: "#CA054D" });
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  test("renders archive cards with inverted front-face colors", () => {
    renderBookList([
      {
        book_id: "archive-book-colors",
        book_title: "Archived Colors",
        is_archived: true,
      },
    ]);

    fireEvent.click(screen.getByRole("tab", { name: /archive/i }));

    const button = screen.getByRole("button", { name: exactName("Archived Colors") });
    expect(button).toHaveStyle({ backgroundColor: "#36839b" });
    expect(within(button).getByText("Archived Colors")).toHaveStyle({ color: "#FFCC00" });
  });

  test("hides the image when it fails to load", async () => {
    renderBookList([
      {
        book_id: "book-4",
        book_title: "Broken Cover",
        cover_url: "https://example.com/broken-cover.png",
        is_archived: false,
      },
    ]);

    const image = screen.getByRole("img", { name: /cover for broken cover/i });
    fireEvent.error(image);

    await waitFor(() => {
      expect(screen.queryByRole("img", { name: /cover for broken cover/i })).not.toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: exactName("Broken Cover") })).toBeInTheDocument();
  });

  test("selects the book when clicked", () => {
    const onSelectBook = jest.fn();

    render(
      <BookList
        {...baseProps}
        books={[
          {
            book_id: "book-5",
            book_title: "Clickable Cover",
            cover_url: "https://example.com/cover.png",
            is_archived: false,
          },
        ]}
        onSelectBook={onSelectBook}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: exactName("Clickable Cover") }));

    expect(onSelectBook).toHaveBeenCalledWith("book-5");
  });

  test("cycles title sorting between ascending and descending", () => {
    renderBookList([
      {
        book_id: "book-2",
        book_title: "Bravo",
        is_archived: false,
      },
      {
        book_id: "book-1",
        book_title: "Alpha",
        is_archived: false,
      },
    ]);

    const titleSortButton = screen.getByRole("button", { name: /title/i });

    expect(getRenderedBookTitles()).toEqual(["Alpha", "Bravo"]);

    fireEvent.click(titleSortButton);
    expect(getRenderedBookTitles()).toEqual(["Bravo", "Alpha"]);

    fireEvent.click(titleSortButton);
    expect(getRenderedBookTitles()).toEqual(["Alpha", "Bravo"]);
  });

  test("cycles created sorting and returns to the default title sort", () => {
    renderBookList([
      {
        book_id: "book-2",
        book_title: "Beta",
        created_at: "2026-04-09T10:00:00Z",
        is_archived: false,
      },
      {
        book_id: "book-1",
        book_title: "Alpha",
        created_at: "2026-04-08T10:00:00Z",
        is_archived: false,
      },
      {
        book_id: "book-3",
        book_title: "Gamma",
        created_at: "2026-04-10T10:00:00Z",
        is_archived: false,
      },
    ]);

    const createdSortButton = screen.getByRole("button", { name: /created/i });
    const titleSortButton = screen.getByRole("button", { name: /title/i });

    fireEvent.click(createdSortButton);
    expect(createdSortButton).toHaveAttribute("aria-pressed", "true");
    expect(titleSortButton).toHaveAttribute("aria-pressed", "false");
    expect(getRenderedBookTitles()).toEqual(["Alpha", "Beta", "Gamma"]);

    fireEvent.click(createdSortButton);
    expect(getRenderedBookTitles()).toEqual(["Gamma", "Beta", "Alpha"]);

    fireEvent.click(createdSortButton);
    expect(titleSortButton).toHaveAttribute("aria-pressed", "true");
    expect(createdSortButton).toHaveAttribute("aria-pressed", "false");
    expect(getRenderedBookTitles()).toEqual(["Alpha", "Beta", "Gamma"]);
  });

  test("retains sort state independently for each tab during the session", () => {
    renderBookList([
      {
        book_id: "shelf-1",
        book_title: "Shelf Alpha",
        created_at: "2026-04-08T10:00:00Z",
        is_archived: false,
        is_favorite: false,
      },
      {
        book_id: "shelf-2",
        book_title: "Shelf Beta",
        created_at: "2026-04-09T10:00:00Z",
        is_archived: false,
        is_favorite: true,
      },
      {
        book_id: "archive-1",
        book_title: "Archive Older",
        created_at: "2026-04-07T10:00:00Z",
        is_archived: true,
      },
      {
        book_id: "archive-2",
        book_title: "Archive Newer",
        created_at: "2026-04-10T10:00:00Z",
        is_archived: true,
      },
    ]);

    const createdSortButton = screen.getByRole("button", { name: /created/i });

    fireEvent.click(createdSortButton);
    fireEvent.click(createdSortButton);
    expect(getRenderedBookTitles()).toEqual(["Shelf Beta", "Shelf Alpha"]);

    fireEvent.click(screen.getByRole("tab", { name: /archive/i }));
    expect(getRenderedBookTitles()).toEqual(["Archive Newer", "Archive Older"]);

    fireEvent.click(createdSortButton);
    expect(getRenderedBookTitles()).toEqual(["Archive Older", "Archive Newer"]);

    fireEvent.click(screen.getByRole("tab", { name: /book shelf/i }));
    expect(getRenderedBookTitles()).toEqual(["Shelf Beta", "Shelf Alpha"]);
  });

  test("archives from the card action without selecting the book", () => {
    const onSelectBook = jest.fn();
    const onUpdateLibraryState = jest.fn();

    render(
      <BookList
        {...baseProps}
        books={[
          {
            book_id: "book-archive",
            book_title: "Archive Me",
            is_archived: false,
          },
        ]}
        onSelectBook={onSelectBook}
        onUpdateLibraryState={onUpdateLibraryState}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /more actions for archive me/i }));
    fireEvent.click(screen.getByRole("button", { name: /move to archive/i }));

    expect(onUpdateLibraryState).toHaveBeenCalledWith("book-archive", { is_archived: true });
    expect(onSelectBook).not.toHaveBeenCalled();
  });

  test("favorites from the card action without selecting the book", () => {
    const onSelectBook = jest.fn();
    const onUpdateLibraryState = jest.fn();

    render(
      <BookList
        {...baseProps}
        books={[
          {
            book_id: "book-favorite",
            book_title: "Favorite Me",
            is_archived: false,
            is_favorite: false,
          },
        ]}
        onSelectBook={onSelectBook}
        onUpdateLibraryState={onUpdateLibraryState}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /more actions for favorite me/i }));
    fireEvent.click(screen.getByRole("button", { name: /add to favorites/i }));

    expect(onUpdateLibraryState).toHaveBeenCalledWith("book-favorite", { is_favorite: true });
    expect(onSelectBook).not.toHaveBeenCalled();
  });

  test("favoriting an archived stale favorite state still sends add-to-favorites", () => {
    const onUpdateLibraryState = jest.fn();

    render(
      <BookList
        {...baseProps}
        books={[
          {
            book_id: "book-archive-favorite-stale",
            book_title: "Archived Stale Favorite",
            is_archived: true,
            is_favorite: true,
          },
        ]}
        onUpdateLibraryState={onUpdateLibraryState}
      />,
    );

    fireEvent.click(screen.getByRole("tab", { name: /archive/i }));
    fireEvent.click(screen.getByRole("button", { name: /more actions for archived stale favorite/i }));

    expect(screen.getByRole("button", { name: /add to favorites/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /add to favorites/i }));

    expect(onUpdateLibraryState).toHaveBeenCalledWith("book-archive-favorite-stale", {
      is_favorite: true,
    });
  });

  test("flips a card open and closed without opening the book", () => {
    const onSelectBook = jest.fn();

    render(
      <BookList
        {...baseProps}
        books={[
          {
            book_id: "book-flip",
            book_title: "Flip Book",
            is_archived: false,
          },
        ]}
        onSelectBook={onSelectBook}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /more actions for flip book/i }));

    expect(screen.getByRole("button", { name: /move to archive/i })).toBeInTheDocument();
    expect(onSelectBook).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: /return to cover for flip book/i }));

    expect(screen.queryByRole("button", { name: /move to archive/i })).not.toBeInTheDocument();
  });

  test("closes the flipped card on outside click", () => {
    renderBookList([
      {
        book_id: "book-outside",
        book_title: "Outside Close",
        is_archived: false,
      },
    ]);

    fireEvent.click(screen.getByRole("button", { name: /more actions for outside close/i }));
    expect(screen.getByRole("button", { name: /move to archive/i })).toBeInTheDocument();

    fireEvent.pointerDown(document.body);

    expect(screen.queryByRole("button", { name: /move to archive/i })).not.toBeInTheDocument();
  });

  test("keeps only one flipped card open at a time", () => {
    renderBookList([
      {
        book_id: "book-a",
        book_title: "First Book",
        is_archived: false,
      },
      {
        book_id: "book-b",
        book_title: "Second Book",
        is_archived: false,
      },
    ]);

    fireEvent.click(screen.getByRole("button", { name: /more actions for first book/i }));
    expect(screen.getByRole("button", { name: /move to archive/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /more actions for second book/i }));

    expect(screen.getAllByRole("button", { name: /move to archive/i })).toHaveLength(1);
    expect(screen.getByRole("button", { name: /return to cover for second book/i })).toBeInTheDocument();
  });

  test("switches across Book Shelf, Favorites, and Archive", () => {
    matchMediaController.setMatches(mobileGridQuery, true);

    renderBookList([
      {
        book_id: "book-6",
        book_title: "Archive Toggle Book",
        is_archived: false,
        is_favorite: false,
      },
      {
        book_id: "book-6b",
        book_title: "Favorite Shelf Book",
        is_archived: false,
        is_favorite: true,
      },
      {
        book_id: "book-7",
        book_title: "Archived Book",
        is_archived: true,
        is_favorite: true,
      },
    ]);

    expect(screen.getByRole("list")).toHaveStyle({ gridTemplateColumns: "1fr" });

    fireEvent.click(screen.getByRole("tab", { name: /favorites/i }));

    expect(screen.getByRole("tab", { name: /favorites/i })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("button", { name: exactName("Favorite Shelf Book") })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: exactName("Archive Toggle Book") })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: exactName("Archived Book") })).not.toBeInTheDocument();
    const favoriteFrontButton = screen.getByRole("button", { name: exactName("Favorite Shelf Book") });
    expect(favoriteFrontButton).toHaveStyle({
      backgroundColor: "#CA054D",
    });
    expect(within(favoriteFrontButton).getByText("Favorite Shelf Book")).toHaveStyle({ color: "#FFCC00" });

    fireEvent.click(screen.getByRole("tab", { name: /archive/i }));

    expect(screen.getByRole("tab", { name: /archive/i })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("button", { name: exactName("Archived Book") })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: exactName("Archive Toggle Book") })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: exactName("Favorite Shelf Book") })).not.toBeInTheDocument();
    expect(screen.getByRole("list")).toHaveStyle({ gridTemplateColumns: "1fr" });
    const archivedFrontButton = screen.getByRole("button", { name: exactName("Archived Book") });
    expect(archivedFrontButton).toHaveStyle({
      backgroundColor: "#36839b",
    });
    expect(within(archivedFrontButton).getByText("Archived Book")).toHaveStyle({ color: "#FFCC00" });

    fireEvent.click(screen.getByRole("button", { name: /more actions for archived book/i }));
    expect(screen.getByRole("button", { name: /restore to book shelf/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /add to favorites/i })).toBeInTheDocument();
    expect(screen.getAllByText("Archived Book")[1]).toHaveStyle({
      color: "#FFCC00",
    });
    expect(screen.getByRole("button", { name: /return to cover for archived book/i })).toHaveStyle({
      backgroundColor: "#FFCC00",
      color: "#CA054D",
    });
    expect(screen.getByRole("button", { name: /restore to book shelf/i })).toHaveStyle({
      backgroundColor: "#FFCC00",
      color: "#CA054D",
    });

    fireEvent.click(screen.getByRole("tab", { name: /book shelf/i }));

    expect(screen.getByRole("tab", { name: /book shelf/i })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("button", { name: exactName("Archive Toggle Book") })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: exactName("Favorite Shelf Book") })).toBeInTheDocument();
  });

  test("renders loading state inline with tabs visible", () => {
    render(<BookList {...baseProps} books={[]} loading />);

    expect(screen.getByRole("tab", { name: /book shelf/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /favorites/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /archive/i })).toBeInTheDocument();
    expect(screen.getByText("Loading books...")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /close modal/i })).not.toBeInTheDocument();
  });

  test("renders error state inline with tabs visible and retry action", () => {
    const onRetry = jest.fn();

    render(<BookList {...baseProps} books={[]} error onRetry={onRetry} />);

    expect(screen.getByRole("tab", { name: /book shelf/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /favorites/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /archive/i })).toBeInTheDocument();
    expect(screen.getByText("Error fetching books. Please try again later.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /retry/i }));

    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  test("shows the favorites empty state text", () => {
    renderBookList([
      {
        book_id: "book-non-favorite",
        book_title: "Not Favorite",
        is_archived: false,
        is_favorite: false,
      },
    ]);

    fireEvent.click(screen.getByRole("tab", { name: /favorites/i }));

    expect(screen.getByText("You don't have any Favorites yet.")).toBeInTheDocument();
  });

  test("equalizes card heights within each desktop row only", async () => {
    const originalGetBoundingClientRect = HTMLElement.prototype.getBoundingClientRect;

    HTMLElement.prototype.getBoundingClientRect = jest.fn(function mockRect() {
      if (this.tagName === "BUTTON" && this.getAttribute("role") !== "tab") {
        if (this.getAttribute("aria-label") === "Row One Short") {
          return { width: 200, height: 180, top: 0, left: 0, right: 200, bottom: 180 };
        }

        if (this.getAttribute("aria-label") === "Row One Tall") {
          return { width: 200, height: 320, top: 0, left: 220, right: 420, bottom: 320 };
        }

        if (this.getAttribute("aria-label") === "Row Two Short") {
          return { width: 200, height: 210, top: 340, left: 0, right: 200, bottom: 550 };
        }

        if (this.getAttribute("aria-label") === "Row Two Tall") {
          return { width: 200, height: 260, top: 340, left: 220, right: 420, bottom: 600 };
        }
      }

      return { width: 0, height: 0, top: 0, left: 0, right: 0, bottom: 0 };
    });

    renderBookList([
      {
        book_id: "row-1-short",
        book_title: "Row One Short",
        is_archived: false,
      },
      {
        book_id: "row-1-tall",
        book_title: "Row One Tall",
        is_archived: false,
      },
      {
        book_id: "row-2-short",
        book_title: "Row Two Short",
        is_archived: false,
      },
      {
        book_id: "row-2-tall",
        book_title: "Row Two Tall",
        is_archived: false,
      },
    ]);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: exactName("Row One Short") })).toHaveStyle({
        height: "320px",
      });
      expect(screen.getByRole("button", { name: exactName("Row One Tall") })).toHaveStyle({
        height: "320px",
      });
      expect(screen.getByRole("button", { name: exactName("Row Two Short") })).toHaveStyle({
        height: "260px",
      });
      expect(screen.getByRole("button", { name: exactName("Row Two Tall") })).toHaveStyle({
        height: "260px",
      });
    });

    HTMLElement.prototype.getBoundingClientRect = originalGetBoundingClientRect;
  });

  test("equalizes archive card heights within each row", async () => {
    const originalGetBoundingClientRect = HTMLElement.prototype.getBoundingClientRect;

    HTMLElement.prototype.getBoundingClientRect = jest.fn(function mockRect() {
      if (this.tagName === "BUTTON" && this.getAttribute("role") !== "tab") {
        if (this.getAttribute("aria-label") === "Archive Short") {
          return { width: 200, height: 190, top: 0, left: 0, right: 200, bottom: 190 };
        }

        if (this.getAttribute("aria-label") === "Archive Tall") {
          return { width: 200, height: 300, top: 0, left: 220, right: 420, bottom: 300 };
        }
      }

      return { width: 0, height: 0, top: 0, left: 0, right: 0, bottom: 0 };
    });

    renderBookList([
      {
        book_id: "archive-short",
        book_title: "Archive Short",
        is_archived: true,
      },
      {
        book_id: "archive-tall",
        book_title: "Archive Tall",
        is_archived: true,
      },
    ]);

    fireEvent.click(screen.getByRole("tab", { name: /archive/i }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: exactName("Archive Short") })).toHaveStyle({
        height: "300px",
      });
      expect(screen.getByRole("button", { name: exactName("Archive Tall") })).toHaveStyle({
        height: "300px",
      });
    });

    HTMLElement.prototype.getBoundingClientRect = originalGetBoundingClientRect;
  });

  test("keeps single-column mobile rows at their own measured heights", async () => {
    const originalGetBoundingClientRect = HTMLElement.prototype.getBoundingClientRect;
    matchMediaController.setMatches(mobileGridQuery, true);

    HTMLElement.prototype.getBoundingClientRect = jest.fn(function mockRect() {
      if (this.tagName === "BUTTON" && this.getAttribute("role") !== "tab") {
        if (this.getAttribute("aria-label") === "Mobile One") {
          return { width: 200, height: 180, top: 0, left: 0, right: 200, bottom: 180 };
        }

        if (this.getAttribute("aria-label") === "Mobile Two") {
          return { width: 200, height: 320, top: 340, left: 0, right: 200, bottom: 660 };
        }

        if (this.getAttribute("aria-label") === "Mobile Three") {
          return { width: 200, height: 240, top: 700, left: 0, right: 200, bottom: 940 };
        }
      }

      return { width: 0, height: 0, top: 0, left: 0, right: 0, bottom: 0 };
    });

    renderBookList([
      {
        book_id: "mobile-one",
        book_title: "Mobile One",
        is_archived: false,
      },
      {
        book_id: "mobile-two",
        book_title: "Mobile Two",
        is_archived: false,
      },
      {
        book_id: "mobile-three",
        book_title: "Mobile Three",
        is_archived: false,
      },
    ]);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: exactName("Mobile One") })).toHaveStyle({
        height: "180px",
      });
      expect(screen.getByRole("button", { name: exactName("Mobile Two") })).toHaveStyle({
        height: "320px",
      });
      expect(screen.getByRole("button", { name: exactName("Mobile Three") })).toHaveStyle({
        height: "240px",
      });
    });

    HTMLElement.prototype.getBoundingClientRect = originalGetBoundingClientRect;
  });

  test("keeps book buttons interactive after a relayout trigger", async () => {
    const originalGetBoundingClientRect = HTMLElement.prototype.getBoundingClientRect;

    HTMLElement.prototype.getBoundingClientRect = jest.fn(function mockRect() {
      if (this.tagName === "BUTTON" && this.getAttribute("role") !== "tab") {
        if (this.getAttribute("aria-label") === "Tall Book") {
          return { width: 200, height: 320, top: 0, left: 220, right: 420, bottom: 320 };
        }

        return { width: 200, height: 180, top: 0, left: 0, right: 200, bottom: 180 };
      }

      return { width: 0, height: 0, top: 0, left: 0, right: 0, bottom: 0 };
    });

    renderBookList([
      {
        book_id: "book-7",
        book_title: "Short Book",
        is_archived: false,
      },
      {
        book_id: "book-8",
        book_title: "Tall Book",
        cover_url: "https://example.com/tall-cover.png",
        is_archived: false,
      },
    ]);

    fireEvent.load(screen.getByRole("img", { name: /cover for tall book/i }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: exactName("Short Book") })).toHaveStyle({
        height: "320px",
      });
      expect(screen.getByRole("button", { name: exactName("Tall Book") })).toHaveStyle({
        height: "320px",
      });
    });

    fireEvent.click(screen.getByRole("button", { name: exactName("Short Book") }));
    expect(baseProps.onSelectBook).toHaveBeenCalledWith("book-7");

    HTMLElement.prototype.getBoundingClientRect = originalGetBoundingClientRect;
  });
});
