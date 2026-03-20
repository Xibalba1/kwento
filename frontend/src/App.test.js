import { act } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import App from "./App";

jest.mock("./config", () => ({
  buildApiUrl: (path) => `http://localhost${path}`,
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
