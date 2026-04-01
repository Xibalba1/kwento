import { act } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import App from "./App";

const mockEnforceCacheBudget = jest.fn();
const mockGetCachedFullBook = jest.fn();
const mockLoadShelfMetadataSync = jest.fn();
const mockSaveFullBookPackage = jest.fn();
const mockSaveShelfMetadata = jest.fn();

jest.mock("./config", () => ({
  buildApiUrl: (path) => `http://localhost${path}`,
}));

jest.mock("./cache/libraryCache", () => ({
  enforceCacheBudget: (...args) => mockEnforceCacheBudget(...args),
  getCachedFullBook: (...args) => mockGetCachedFullBook(...args),
  loadShelfMetadataSync: (...args) => mockLoadShelfMetadataSync(...args),
  saveFullBookPackage: (...args) => mockSaveFullBookPackage(...args),
  saveShelfMetadata: (...args) => mockSaveShelfMetadata(...args),
}));

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
  global.URL.createObjectURL = jest.fn((value) => `blob:${String(value)}`);
  global.URL.revokeObjectURL = jest.fn();
  mockEnforceCacheBudget.mockResolvedValue(undefined);
  mockGetCachedFullBook.mockResolvedValue(null);
  mockLoadShelfMetadataSync.mockImplementation(() => {
    const raw = window.localStorage.getItem("kwento_shelf_metadata_v1");
    return raw ? JSON.parse(raw) : null;
  });
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
      },
    ],
  });

  await act(async () => {
    render(<App />);
  });

  expect(screen.getByText("Kwento")).toBeInTheDocument();
  expect(screen.getByText("Make your story!")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /generate book/i })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /library book/i })).toBeInTheDocument();

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
          cover_url: "https://example.com/cached-cover.png",
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

  expect(screen.getByRole("button", { name: /cached shelf book/i })).toBeInTheDocument();
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
        },
      ],
    });
  });

  await waitFor(() => {
    expect(screen.getByRole("button", { name: /remote shelf book/i })).toBeInTheDocument();
  });
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

  expect(screen.getByRole("button", { name: /offline shelf book/i })).toBeInTheDocument();

  await waitFor(() => {
    expect(global.fetch).toHaveBeenCalledWith("http://localhost/books/", {
      method: "GET",
      headers: { "Content-Type": "application/json" },
    });
  });

  expect(screen.queryByText(/error fetching books/i)).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: /offline shelf book/i })).toBeInTheDocument();
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

  const bookButton = await screen.findByRole("button", { name: /repeat click book/i });

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
      }),
    });
  });

  await waitFor(() => {
    expect(global.fetch).toHaveBeenCalledTimes(3);
  });
});

test("revokes cached book object URLs when the modal closes, not when it opens", async () => {
  mockGetCachedFullBook.mockResolvedValue({
    book_id: "book-2",
    book_title: "Cached Modal Book",
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
      },
    ],
  });

  await act(async () => {
    render(<App />);
  });

  fireEvent.click(await screen.findByRole("button", { name: /cached modal book/i }));

  expect(await screen.findByRole("button", { name: /close modal/i })).toBeInTheDocument();
  expect(global.URL.revokeObjectURL).not.toHaveBeenCalled();

  fireEvent.click(screen.getByRole("button", { name: /close modal/i }));

  await waitFor(() => {
    expect(global.URL.revokeObjectURL).toHaveBeenCalledWith("blob:book-2-cover");
    expect(global.URL.revokeObjectURL).toHaveBeenCalledWith("blob:book-2-page-1");
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
