import { act } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import App from "./App";

jest.mock("./config", () => ({
  buildApiUrl: (path) => `http://localhost${path}`,
}));

beforeEach(() => {
  global.fetch = jest.fn().mockResolvedValue({
    ok: true,
    json: async () => [],
  });
});

afterEach(() => {
  jest.resetAllMocks();
});

test("renders the app header and library entry point", async () => {
  await act(async () => {
    render(<App />);
  });

  expect(screen.getByText("Kwento")).toBeInTheDocument();
  expect(screen.getByText("Make your story!")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /my book shelf/i })).toBeInTheDocument();

  await waitFor(() => {
    expect(global.fetch).toHaveBeenCalledWith("http://localhost/books/", {
      method: "GET",
      headers: { "Content-Type": "application/json" },
    });
  });
});
