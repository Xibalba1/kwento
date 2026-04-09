import { act } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import App from "./App";

const mockEnforceCacheBudget = jest.fn();
const mockEnforceShelfCoverBudget = jest.fn();
const mockGetCachedShelfCovers = jest.fn();
const mockGetCachedFullBook = jest.fn();
const mockDeleteShelfCover = jest.fn();
const mockLoadShelfMetadataSync = jest.fn();
const mockSaveShelfCover = jest.fn();
const mockSaveFullBookPackage = jest.fn();
const mockSaveShelfMetadata = jest.fn();

jest.mock("./config", () => ({
  buildApiUrl: (path) => `http://localhost${path}`,
}));

jest.mock("./cache/libraryCache", () => ({
  enforceCacheBudget: (...args) => mockEnforceCacheBudget(...args),
  enforceShelfCoverBudget: (...args) => mockEnforceShelfCoverBudget(...args),
  getCachedShelfCovers: (...args) => mockGetCachedShelfCovers(...args),
  getCachedFullBook: (...args) => mockGetCachedFullBook(...args),
  deleteShelfCover: (...args) => mockDeleteShelfCover(...args),
  loadShelfMetadataSync: (...args) => mockLoadShelfMetadataSync(...args),
  saveShelfCover: (...args) => mockSaveShelfCover(...args),
  saveFullBookPackage: (...args) => mockSaveFullBookPackage(...args),
  saveShelfMetadata: (...args) => mockSaveShelfMetadata(...args),
}));

const exactName = (label) => new RegExp(`^${label}$`, "i");

const createDeferred = () => {
  let resolvePromise;
  let rejectPromise;

  const promise = new Promise((resolve, reject) => {
    resolvePromise = resolve;
    rejectPromise = reject;
  });

  return {
    promise,
    resolve: resolvePromise,
    reject: rejectPromise,
  };
};

beforeEach(() => {
  window.localStorage.clear();
  window.alert = jest.fn();
  global.URL.createObjectURL = jest.fn((value) => `blob:${String(value)}`);
  global.URL.revokeObjectURL = jest.fn();
  mockEnforceCacheBudget.mockResolvedValue(undefined);
  mockEnforceShelfCoverBudget.mockResolvedValue(undefined);
  mockGetCachedShelfCovers.mockResolvedValue(new Map());
  mockGetCachedFullBook.mockResolvedValue(null);
  mockDeleteShelfCover.mockResolvedValue(undefined);
  mockLoadShelfMetadataSync.mockImplementation(() => {
    const raw = window.localStorage.getItem("kwento_shelf_metadata_v1");
    return raw ? JSON.parse(raw) : null;
  });
  mockSaveShelfCover.mockResolvedValue(undefined);
  mockSaveFullBookPackage.mockResolvedValue(undefined);
  mockSaveShelfMetadata.mockResolvedValue(undefined);
  global.fetch = jest.fn().mockResolvedValue({
    ok: true,
    json: async () => [],
  });
});

afterEach(() => {
  jest.resetAllMocks();
});

test("renders the app header and library entry point", async () => {
  global.fetch.mockResolvedValue({
    ok: true,
    json: async () => [
      {
        book_id: "book-1",
        book_title: "Library Book",
        is_archived: false,
      },
    ],
  });

  await act(async () => {
    render(<App />);
  });

  expect(screen.getByText("Kwento")).toBeInTheDocument();
  expect(screen.getByText("Make your story!")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /generate book/i })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: exactName("Library Book") })).toBeInTheDocument();

  await waitFor(() => {
    expect(global.fetch).toHaveBeenCalledWith("http://localhost/books/", {
      method: "GET",
      headers: { "Content-Type": "application/json" },
    });
  });
});

test("renders cached shelf metadata before the background refresh resolves", async () => {
  window.localStorage.setItem(
    "kwento_shelf_metadata_v1",
    JSON.stringify({
      version: 1,
      books: [
        {
          book_id: "cached-book-1",
          book_title: "Cached Shelf Book",
          created_at: "2026-04-08T10:00:00Z",
          cover_url: "https://example.com/cached-cover.png",
          is_archived: false,
        },
      ],
      updatedAt: Date.now(),
      expiresAt: Date.now() + 1000,
    }),
  );

  const booksRequest = createDeferred();
  global.fetch.mockReturnValue(booksRequest.promise);

  await act(async () => {
    render(<App />);
  });

  expect(screen.getByRole("button", { name: exactName("Cached Shelf Book") })).toBeInTheDocument();
  expect(global.fetch).toHaveBeenCalledWith("http://localhost/books/", {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });

  await act(async () => {
    booksRequest.resolve({
      ok: true,
      json: async () => [
        {
          book_id: "remote-book-1",
          book_title: "Remote Shelf Book",
          created_at: "2026-04-09T10:00:00Z",
          is_archived: false,
        },
      ],
    });
  });

  await waitFor(() => {
    expect(screen.getByRole("button", { name: exactName("Remote Shelf Book") })).toBeInTheDocument();
  });
});

test("suppresses stale cached shelf covers until refreshed shelf data arrives", async () => {
  const now = Date.now();
  mockLoadShelfMetadataSync.mockReturnValue({
    version: 1,
    books: [
      {
        book_id: "cached-book-stale-cover",
        book_title: "Cached Shelf Book",
        cover_url: null,
        cover_expires_at: new Date(now - 60_000).toISOString(),
        is_archived: false,
      },
    ],
    updatedAt: now,
    expiresAt: now + 1_000,
  });

  const booksRequest = createDeferred();
  global.fetch.mockReturnValue(booksRequest.promise);

  await act(async () => {
    render(<App />);
  });

  expect(screen.getByRole("button", { name: exactName("Cached Shelf Book") })).toBeInTheDocument();
  expect(screen.queryByRole("img", { name: /cover for cached shelf book/i })).not.toBeInTheDocument();

  await act(async () => {
    booksRequest.resolve({
      ok: true,
      json: async () => [
        {
          book_id: "cached-book-stale-cover",
          book_title: "Cached Shelf Book",
          cover_url: "https://example.com/fresh-cover.png",
          cover_expires_at: new Date(now + 60 * 60 * 1000).toISOString(),
          is_archived: false,
        },
      ],
    });
  });

  const image = await screen.findByRole("img", { name: /cover for cached shelf book/i });
  expect(image).toHaveAttribute("src", "https://example.com/fresh-cover.png");
});

test("keeps cached shelf metadata visible when the background refresh fails", async () => {
  window.localStorage.setItem(
    "kwento_shelf_metadata_v1",
    JSON.stringify({
      version: 1,
      books: [
        {
          book_id: "cached-book-2",
          book_title: "Offline Shelf Book",
        },
      ],
      updatedAt: Date.now(),
      expiresAt: Date.now() + 1000,
    }),
  );

  global.fetch.mockRejectedValue(new Error("network down"));

  await act(async () => {
    render(<App />);
  });

  expect(screen.getByRole("button", { name: exactName("Offline Shelf Book") })).toBeInTheDocument();

  await waitFor(() => {
    expect(global.fetch).toHaveBeenCalledWith("http://localhost/books/", {
      method: "GET",
      headers: { "Content-Type": "application/json" },
    });
  });

  expect(screen.queryByText(/error fetching books/i)).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: exactName("Offline Shelf Book") })).toBeInTheDocument();
});

test("deduplicates repeated clicks while the same book is still opening", async () => {
  const bookDetailsRequest = createDeferred();

  global.fetch
    .mockResolvedValueOnce({
      ok: true,
      json: async () => [
        {
          book_id: "book-1",
          book_title: "Repeat Click Book",
          json_url: "https://example.com/book-1.json",
          is_archived: false,
        },
      ],
    })
    .mockReturnValueOnce(bookDetailsRequest.promise)
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        pages: [{ page: 1, text: "Once upon a time" }],
      }),
    });

  await act(async () => {
    render(<App />);
  });

  const bookButton = await screen.findByRole("button", { name: exactName("Repeat Click Book") });

  await act(async () => {
    fireEvent.click(bookButton);
    fireEvent.click(bookButton);
    fireEvent.click(bookButton);
  });

  expect(mockGetCachedFullBook).toHaveBeenCalledTimes(1);
  expect(global.fetch).toHaveBeenCalledTimes(2);
  expect(global.fetch).toHaveBeenNthCalledWith(2, "http://localhost/books/book-1/", {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });

  await act(async () => {
    bookDetailsRequest.resolve({
      ok: true,
      json: async () => ({
        book_id: "book-1",
        book_title: "Repeat Click Book",
        json_url: "https://example.com/book-1.json",
        images: [],
        is_archived: false,
      }),
    });
  });

  await waitFor(() => {
    expect(global.fetch).toHaveBeenCalledTimes(3);
  });
});

test("disables generation controls while a book is generating", async () => {
  const generateRequest = createDeferred();

  global.fetch
    .mockResolvedValueOnce({
      ok: true,
      json: async () => [],
    })
    .mockReturnValueOnce(generateRequest.promise);

  await act(async () => {
    render(<App />);
  });

  const themeInput = screen.getByPlaceholderText(/enter a theme for your book/i);
  const generateButton = screen.getByRole("button", { name: /generate book/i });

  fireEvent.change(themeInput, { target: { value: "Sky pirates" } });

  await act(async () => {
    fireEvent.click(generateButton);
  });

  expect(generateButton).toBeDisabled();
  expect(screen.getByRole("button", { name: /generating/i })).toBeDisabled();
  expect(themeInput).toBeDisabled();
  expect(themeInput).toHaveStyle({
    backgroundColor: "#E5E7EB",
    color: "#4B5563",
    cursor: "not-allowed",
    opacity: "1",
  });
  expect(themeInput).toHaveValue("Sky pirates");
});

test("clears the theme after a successful generation", async () => {
  global.fetch
    .mockResolvedValueOnce({
      ok: true,
      json: async () => [],
    })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        book_id: "generated-book-1",
        book_title: "Generated Book",
        created_at: "2026-04-09T12:00:00Z",
        json_url: "https://example.com/generated-book-1.json",
        cover: {
          url: "https://example.com/generated-book-1-cover.png",
        },
        images: [],
        is_archived: false,
      }),
    })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        pages: [
          {
            page_number: 1,
            content: {
              text_content_of_this_page: "Generated page text",
            },
          },
        ],
      }),
    });

  await act(async () => {
    render(<App />);
  });

  const themeInput = screen.getByPlaceholderText(/enter a theme for your book/i);

  fireEvent.change(themeInput, { target: { value: "Moonlit jungle" } });

  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: /generate book/i }));
  });

  await waitFor(() => {
    expect(global.fetch).toHaveBeenNthCalledWith(2, "http://localhost/books/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ theme: "Moonlit jungle" }),
    });
  });

  await screen.findByRole("button", { name: /close modal/i });
  expect(themeInput).toHaveValue("");

  await waitFor(() => {
    expect(mockSaveFullBookPackage).toHaveBeenCalledWith(
      expect.objectContaining({
        book_id: "generated-book-1",
        created_at: "2026-04-09T12:00:00Z",
      }),
    );
  });
});

test("preserves created_at when hydrating and refreshing shelf metadata", async () => {
  window.localStorage.setItem(
    "kwento_shelf_metadata_v1",
    JSON.stringify({
      version: 1,
      books: [
        {
          book_id: "created-cache-book",
          book_title: "Created Cache Book",
          created_at: "2026-04-07T10:00:00Z",
          is_archived: false,
        },
      ],
      updatedAt: Date.now(),
      expiresAt: Date.now() + 1000,
    }),
  );

  global.fetch.mockResolvedValueOnce({
    ok: true,
    json: async () => [
      {
        book_id: "created-cache-book",
        book_title: "Created Cache Book",
        created_at: "2026-04-08T10:00:00Z",
        is_archived: false,
      },
    ],
  });

  await act(async () => {
    render(<App />);
  });

  expect(screen.getByRole("button", { name: exactName("Created Cache Book") })).toBeInTheDocument();

  await waitFor(() => {
    expect(mockSaveShelfMetadata).toHaveBeenLastCalledWith(
      expect.arrayContaining([
        expect.objectContaining({
          book_id: "created-cache-book",
          created_at: "2026-04-08T10:00:00Z",
        }),
      ]),
    );
  });
});

test("clears the theme after a failed generation request", async () => {
  global.fetch
    .mockResolvedValueOnce({
      ok: true,
      json: async () => [],
    })
    .mockResolvedValueOnce({
      ok: false,
      json: async () => ({}),
    });

  await act(async () => {
    render(<App />);
  });

  const themeInput = screen.getByPlaceholderText(/enter a theme for your book/i);

  fireEvent.change(themeInput, { target: { value: "Stormy forest" } });

  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: /generate book/i }));
  });

  await waitFor(() => {
    expect(window.alert).toHaveBeenCalledWith("Error generating book. Please try again.");
  });
  expect(themeInput).toHaveValue("");
});

test("does not clear the theme when empty-theme validation blocks generation", async () => {
  global.fetch.mockResolvedValueOnce({
    ok: true,
    json: async () => [],
  });

  await act(async () => {
    render(<App />);
  });

  const themeInput = screen.getByPlaceholderText(/enter a theme for your book/i);
  const generateButton = screen.getByRole("button", { name: /generate book/i });

  fireEvent.change(themeInput, { target: { value: "   " } });

  await act(async () => {
    fireEvent.click(generateButton);
  });

  expect(window.alert).toHaveBeenCalledWith("Please enter a theme to generate a book.");
  expect(themeInput).toHaveValue("   ");
  expect(global.fetch).toHaveBeenCalledTimes(1);
});

test("revokes cached book object URLs when the modal closes, not when it opens", async () => {
  mockGetCachedFullBook.mockResolvedValue({
    book_id: "book-2",
    book_title: "Cached Modal Book",
    json_url: "https://example.com/stale-book-2.json",
    __cachedObjectUrls: ["blob:book-2-cover", "blob:book-2-page-1"],
    pages: [
      {
        page_number: 1,
        content: {
          text_content_of_this_page: "Cached page text",
        },
      },
    ],
    images: [
      {
        page: 1,
        url: "blob:book-2-page-1",
      },
    ],
  });

  global.fetch.mockResolvedValueOnce({
    ok: true,
    json: async () => [
      {
        book_id: "book-2",
        book_title: "Cached Modal Book",
        json_url: "https://example.com/book-2.json",
        is_archived: false,
      },
    ],
  });

  await act(async () => {
    render(<App />);
  });

  fireEvent.click(await screen.findByRole("button", { name: exactName("Cached Modal Book") }));

  expect(await screen.findByRole("button", { name: /close modal/i })).toBeInTheDocument();
  expect(global.URL.revokeObjectURL).not.toHaveBeenCalled();
  expect(global.fetch).toHaveBeenCalledTimes(1);

  fireEvent.click(screen.getByRole("button", { name: /close modal/i }));

  await waitFor(() => {
    expect(global.URL.revokeObjectURL).toHaveBeenCalledWith("blob:book-2-cover");
    expect(global.URL.revokeObjectURL).toHaveBeenCalledWith("blob:book-2-page-1");
  });
});

test("prefers fresh detail asset URLs over stale book json asset URLs", async () => {
  global.fetch
    .mockResolvedValueOnce({
      ok: true,
      json: async () => [
        {
          book_id: "book-fresh-assets",
          book_title: "Fresh Assets Book",
          cover_url: "https://example.com/fresh-shelf-cover.png",
          is_archived: false,
        },
      ],
    })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        book_id: "book-fresh-assets",
        book_title: "Fresh Assets Book",
        json_url: "https://example.com/fresh-book.json",
        cover: {
          url: "https://example.com/fresh-detail-cover.png",
        },
        images: [
          {
            page: 1,
            url: "https://example.com/fresh-page-1.png",
          },
        ],
        is_archived: false,
      }),
    })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        book_id: "book-fresh-assets",
        book_title: "Fresh Assets Book",
        cover: {
          url: "https://example.com/stale-json-cover.png",
        },
        images: [
          {
            page: 1,
            url: "https://example.com/stale-json-page-1.png",
          },
        ],
        pages: [
          {
            page_number: 1,
            content: {
              text_content_of_this_page: "Fresh page text",
            },
          },
        ],
      }),
    });

  await act(async () => {
    render(<App />);
  });

  fireEvent.click(await screen.findByRole("button", { name: exactName("Fresh Assets Book") }));

  await screen.findByRole("button", { name: /close modal/i });

  await waitFor(() => {
    expect(mockSaveFullBookPackage).toHaveBeenCalledWith(
      expect.objectContaining({
        book_id: "book-fresh-assets",
        json_url: "https://example.com/fresh-book.json",
        cover_url: "https://example.com/fresh-detail-cover.png",
        cover: expect.objectContaining({
          url: "https://example.com/fresh-detail-cover.png",
        }),
        images: [
          expect.objectContaining({
            page: 1,
            url: "https://example.com/fresh-page-1.png",
          }),
        ],
      }),
    );
  });
});

test("renders shelf covers from the remote cover_url", async () => {
  global.fetch.mockResolvedValueOnce({
    ok: true,
    json: async () => [
      {
        book_id: "book-remote-cover",
        book_title: "Remote Cover Book",
        cover_url: "https://example.com/remote-cover.png",
        is_archived: false,
      },
    ],
  });

  await act(async () => {
    render(<App />);
  });

  const image = await screen.findByRole("img", { name: /cover for remote cover book/i });
  expect(image).toHaveAttribute("src", "https://example.com/remote-cover.png");
  expect(global.URL.createObjectURL).not.toHaveBeenCalled();
});

test("merges cached shelf cover blob URLs after the initial shelf render", async () => {
  mockGetCachedShelfCovers.mockResolvedValue(
    new Map([
      [
        "book-remote-cover",
        {
          objectUrl: "blob:shelf-cover-1",
          sourceUrl: "https://example.com/remote-cover.png",
        },
      ],
    ]),
  );

  global.fetch.mockResolvedValueOnce({
    ok: true,
    json: async () => [
      {
        book_id: "book-remote-cover",
        book_title: "Remote Cover Book",
        cover_url: "https://example.com/remote-cover.png",
        is_archived: false,
      },
    ],
  });

  await act(async () => {
    render(<App />);
  });

  expect(await screen.findByRole("button", { name: exactName("Remote Cover Book") })).toBeInTheDocument();

  await waitFor(() => {
    expect(screen.getByRole("img", { name: /cover for remote cover book/i })).toHaveAttribute(
      "src",
      "blob:shelf-cover-1",
    );
  });
});

test("warms shelf covers in the background after shelf metadata renders", async () => {
  global.fetch.mockResolvedValueOnce({
    ok: true,
    json: async () => [
      {
        book_id: "book-remote-cover",
        book_title: "Remote Cover Book",
        cover_url: "https://example.com/remote-cover.png",
        cover_expires_at: new Date(Date.now() + 60 * 60 * 1000).toISOString(),
        is_archived: false,
      },
    ],
  });

  await act(async () => {
    render(<App />);
  });

  expect(await screen.findByRole("img", { name: /cover for remote cover book/i })).toHaveAttribute(
    "src",
    "https://example.com/remote-cover.png",
  );

  await waitFor(() => {
    expect(mockSaveShelfCover).toHaveBeenCalledWith(
      expect.objectContaining({
        book_id: "book-remote-cover",
        remote_cover_url: "https://example.com/remote-cover.png",
      }),
    );
  });

  expect(mockEnforceShelfCoverBudget).toHaveBeenCalled();
});

test("defers shelf cover warming while full-book work is in flight", async () => {
  jest.useFakeTimers();
  const cachedBookRequest = createDeferred();
  mockGetCachedFullBook.mockReturnValueOnce(cachedBookRequest.promise);
  mockLoadShelfMetadataSync.mockReturnValue({
    version: 1,
    books: [
      {
        book_id: "book-remote-cover",
        book_title: "Remote Cover Book",
        cover_url: "https://example.com/remote-cover.png",
        remote_cover_url: "https://example.com/remote-cover.png",
        cover_expires_at: new Date(Date.now() + 60 * 60 * 1000).toISOString(),
        remote_cover_expires_at: new Date(Date.now() + 60 * 60 * 1000).toISOString(),
        is_archived: false,
      },
    ],
    updatedAt: Date.now(),
    expiresAt: Date.now() + 1_000,
  });
  global.fetch.mockReturnValue(createDeferred().promise);

  await act(async () => {
    render(<App />);
  });

  const bookButton = await screen.findByRole("button", { name: exactName("Remote Cover Book") });

  await act(async () => {
    fireEvent.click(bookButton);
  });

  await act(async () => {
    jest.runOnlyPendingTimers();
  });
  expect(mockSaveShelfCover).not.toHaveBeenCalled();

  await act(async () => {
    cachedBookRequest.resolve(null);
  });

  jest.useRealTimers();
});

test("archives a shelf book and moves it to the archive tab", async () => {
  global.fetch
    .mockResolvedValueOnce({
      ok: true,
      json: async () => [
        {
          book_id: "book-archive-1",
          book_title: "Archive Candidate",
          is_archived: false,
          is_favorite: true,
        },
      ],
    })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        book_id: "book-archive-1",
        book_title: "Archive Candidate",
        is_archived: true,
        is_favorite: false,
        json_url: "https://example.com/book-archive-1.json",
        images: [],
      }),
    });

  await act(async () => {
    render(<App />);
  });

  await act(async () => {
    fireEvent.click(await screen.findByRole("button", {
      name: /more actions for archive candidate/i,
    }));
  });

  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: /move to archive/i }));
  });

  await waitFor(() => {
    expect(global.fetch).toHaveBeenLastCalledWith("http://localhost/books/book-archive-1/library-state/", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_archived: true }),
    });
  });

  await act(async () => {
    fireEvent.click(screen.getByRole("tab", { name: /archive/i }));
  });

  expect(await screen.findByRole("button", { name: exactName("Archive Candidate") })).toBeInTheDocument();
});

test("favorites a shelf book and shows it in the favorites tab", async () => {
  global.fetch
    .mockResolvedValueOnce({
      ok: true,
      json: async () => [
        {
          book_id: "book-favorite-1",
          book_title: "Favorite Candidate",
          is_archived: false,
          is_favorite: false,
        },
      ],
    })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        book_id: "book-favorite-1",
        book_title: "Favorite Candidate",
        is_archived: false,
        is_favorite: true,
        json_url: "https://example.com/book-favorite-1.json",
        images: [],
      }),
    });

  await act(async () => {
    render(<App />);
  });

  await act(async () => {
    fireEvent.click(await screen.findByRole("button", {
      name: /more actions for favorite candidate/i,
    }));
  });

  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: /add to favorites/i }));
  });

  await waitFor(() => {
    expect(global.fetch).toHaveBeenLastCalledWith("http://localhost/books/book-favorite-1/library-state/", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_favorite: true }),
    });
  });

  await act(async () => {
    fireEvent.click(screen.getByRole("tab", { name: /favorites/i }));
  });

  expect(await screen.findByRole("button", { name: exactName("Favorite Candidate") })).toBeInTheDocument();
});

test("favoriting an archived book restores it to shelf and favorites", async () => {
  global.fetch
    .mockResolvedValueOnce({
      ok: true,
      json: async () => [
        {
          book_id: "book-favorite-archive-1",
          book_title: "Archived Favorite Candidate",
          is_archived: true,
          is_favorite: false,
        },
      ],
    })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        book_id: "book-favorite-archive-1",
        book_title: "Archived Favorite Candidate",
        is_archived: false,
        is_favorite: true,
        json_url: "https://example.com/book-favorite-archive-1.json",
        images: [],
      }),
    });

  await act(async () => {
    render(<App />);
  });

  await act(async () => {
    fireEvent.click(screen.getByRole("tab", { name: /archive/i }));
  });

  await act(async () => {
    fireEvent.click(await screen.findByRole("button", {
      name: /more actions for archived favorite candidate/i,
    }));
  });

  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: /add to favorites/i }));
  });

  await waitFor(() => {
    expect(global.fetch).toHaveBeenLastCalledWith(
      "http://localhost/books/book-favorite-archive-1/library-state/",
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_favorite: true }),
      },
    );
  });

  await act(async () => {
    fireEvent.click(screen.getByRole("tab", { name: /book shelf/i }));
  });

  expect(await screen.findByRole("button", { name: exactName("Archived Favorite Candidate") })).toBeInTheDocument();

  await act(async () => {
    fireEvent.click(screen.getByRole("tab", { name: /favorites/i }));
  });

  expect(await screen.findByRole("button", { name: exactName("Archived Favorite Candidate") })).toBeInTheDocument();
});

test("favoriting an archived book with stale favorite state removes it from archive immediately", async () => {
  const patchRequest = createDeferred();

  global.fetch
    .mockResolvedValueOnce({
      ok: true,
      json: async () => [
        {
          book_id: "book-stale-archive-favorite-1",
          book_title: "Stale Archived Favorite Candidate",
          is_archived: true,
          is_favorite: true,
        },
      ],
    })
    .mockReturnValueOnce(patchRequest.promise);

  await act(async () => {
    render(<App />);
  });

  await act(async () => {
    fireEvent.click(screen.getByRole("tab", { name: /archive/i }));
  });

  expect(await screen.findByRole("button", { name: exactName("Stale Archived Favorite Candidate") })).toBeInTheDocument();

  await act(async () => {
    fireEvent.click(screen.getByRole("button", {
      name: /more actions for stale archived favorite candidate/i,
    }));
  });

  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: /add to favorites/i }));
  });

  expect(screen.queryByRole("button", { name: exactName("Stale Archived Favorite Candidate") })).not.toBeInTheDocument();
  expect(screen.getByText("Archive is empty")).toBeInTheDocument();

  await act(async () => {
    patchRequest.resolve({
      ok: true,
      json: async () => ({
        book_id: "book-stale-archive-favorite-1",
        book_title: "Stale Archived Favorite Candidate",
        is_archived: false,
        is_favorite: true,
        json_url: "https://example.com/book-stale-archive-favorite-1.json",
        images: [],
      }),
    });
  });

  await act(async () => {
    fireEvent.click(screen.getByRole("tab", { name: /favorites/i }));
  });

  expect(await screen.findByRole("button", { name: exactName("Stale Archived Favorite Candidate") })).toBeInTheDocument();
});
