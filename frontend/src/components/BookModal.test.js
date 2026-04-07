import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import BookModal from "./BookModal";

const createBook = (overrides = {}) => ({
  book_id: "book-1",
  book_title: "Placeholder Book",
  pages: [
    {
      page_number: 1,
      content: {
        text_content_of_this_page: "Page one text.",
      },
    },
    {
      page_number: 2,
      content: {
        text_content_of_this_page: "Page two text.",
      },
    },
  ],
  images: [
    {
      page: 1,
      url: "blob:page-1",
    },
    {
      page: 2,
      url: "blob:page-2",
    },
  ],
  ...overrides,
});

describe("BookModal", () => {
  test("does not render archive actions inside the modal", () => {
    render(<BookModal book={createBook({ is_archived: false })} onClose={jest.fn()} />);

    expect(screen.queryByRole("button", { name: /archive/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /restore/i })).not.toBeInTheDocument();
  });

  test("shows only the placeholder until the current page image loads", () => {
    render(<BookModal book={createBook()} onClose={jest.fn()} />);

    expect(screen.getByTestId("page-illustration-placeholder")).toHaveTextContent(
      "page 1 illustration",
    );

    const image = screen.getByRole("img", { name: /illustration for page 1/i });
    expect(image).toHaveStyle({ opacity: "0" });

    fireEvent.load(image, {
      currentTarget: {
        naturalWidth: 1200,
        naturalHeight: 900,
      },
    });

    expect(screen.queryByTestId("page-illustration-placeholder")).not.toBeInTheDocument();
    expect(screen.getByRole("img", { name: /illustration for page 1/i })).toHaveStyle({
      opacity: "1",
    });
  });

  test("resets to the next page placeholder before that page image loads", () => {
    render(<BookModal book={createBook()} onClose={jest.fn()} />);

    const firstImage = screen.getByRole("img", { name: /illustration for page 1/i });
    fireEvent.load(firstImage, {
      currentTarget: {
        naturalWidth: 1200,
        naturalHeight: 900,
      },
    });

    fireEvent.click(screen.getByRole("button", { name: /next page/i }));

    expect(screen.getByTestId("page-illustration-placeholder")).toHaveTextContent(
      "page 2 illustration",
    );
    expect(screen.queryByRole("img", { name: /illustration for page 1/i })).not.toBeInTheDocument();

    const secondImage = screen.getByRole("img", { name: /illustration for page 2/i });
    expect(secondImage).toHaveStyle({ opacity: "0" });
  });

  test("shows a previously loaded illustration immediately when navigating back", () => {
    render(<BookModal book={createBook()} onClose={jest.fn()} />);

    const firstImage = screen.getByRole("img", { name: /illustration for page 1/i });
    fireEvent.load(firstImage, {
      currentTarget: {
        naturalWidth: 1200,
        naturalHeight: 900,
      },
    });

    fireEvent.click(screen.getByRole("button", { name: /next page/i }));

    const secondImage = screen.getByRole("img", { name: /illustration for page 2/i });
    fireEvent.load(secondImage, {
      currentTarget: {
        naturalWidth: 1200,
        naturalHeight: 900,
      },
    });

    fireEvent.click(screen.getByRole("button", { name: /previous page/i }));

    expect(screen.queryByTestId("page-illustration-placeholder")).not.toBeInTheDocument();
    expect(screen.getByRole("img", { name: /illustration for page 1/i })).toHaveStyle({
      opacity: "1",
    });
  });

  test("promotes a cached complete illustration without waiting for a new load event", async () => {
    const completeDescriptor = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype, "complete");
    const naturalWidthDescriptor = Object.getOwnPropertyDescriptor(
      HTMLImageElement.prototype,
      "naturalWidth",
    );
    const naturalHeightDescriptor = Object.getOwnPropertyDescriptor(
      HTMLImageElement.prototype,
      "naturalHeight",
    );

    try {
      Object.defineProperty(HTMLImageElement.prototype, "complete", {
        configurable: true,
        get() {
          return true;
        },
      });
      Object.defineProperty(HTMLImageElement.prototype, "naturalWidth", {
        configurable: true,
        get() {
          return 1200;
        },
      });
      Object.defineProperty(HTMLImageElement.prototype, "naturalHeight", {
        configurable: true,
        get() {
          return 900;
        },
      });

      render(<BookModal book={createBook()} onClose={jest.fn()} />);

      await waitFor(() => {
        expect(screen.queryByTestId("page-illustration-placeholder")).not.toBeInTheDocument();
        expect(screen.getByRole("img", { name: /illustration for page 1/i })).toHaveStyle({
          opacity: "1",
        });
      });
    } finally {
      if (completeDescriptor) {
        Object.defineProperty(HTMLImageElement.prototype, "complete", completeDescriptor);
      }
      if (naturalWidthDescriptor) {
        Object.defineProperty(HTMLImageElement.prototype, "naturalWidth", naturalWidthDescriptor);
      }
      if (naturalHeightDescriptor) {
        Object.defineProperty(HTMLImageElement.prototype, "naturalHeight", naturalHeightDescriptor);
      }
    }
  });

  test("keeps the placeholder visible when an illustration is missing or fails", () => {
    const { rerender } = render(
      <BookModal
        book={createBook({
          images: [],
        })}
        onClose={jest.fn()}
      />,
    );

    expect(screen.getByTestId("page-illustration-placeholder")).toHaveTextContent(
      "page 1 illustration",
    );
    expect(screen.queryByRole("img")).not.toBeInTheDocument();

    rerender(
      <BookModal
        book={createBook({
          images: [{ page: 1, url: "blob:broken-page-1" }],
        })}
        onClose={jest.fn()}
      />,
    );

    const brokenImage = screen.getByRole("img", { name: /illustration for page 1/i });
    fireEvent.error(brokenImage);

    expect(screen.getByTestId("page-illustration-placeholder")).toHaveTextContent(
      "page 1 illustration",
    );
    expect(screen.queryByRole("img", { name: /illustration for page 1/i })).not.toBeInTheDocument();
  });

  test("preserves an illustration error state when revisiting the same page", () => {
    render(<BookModal book={createBook()} onClose={jest.fn()} />);

    const firstImage = screen.getByRole("img", { name: /illustration for page 1/i });
    fireEvent.error(firstImage);

    expect(screen.getByTestId("page-illustration-placeholder")).toHaveTextContent(
      "page 1 illustration",
    );
    expect(screen.queryByRole("img", { name: /illustration for page 1/i })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /next page/i }));
    expect(screen.getByRole("img", { name: /illustration for page 2/i })).toHaveStyle({
      opacity: "0",
    });

    fireEvent.click(screen.getByRole("button", { name: /previous page/i }));
    expect(screen.getByTestId("page-illustration-placeholder")).toHaveTextContent(
      "page 1 illustration",
    );
    expect(screen.queryByRole("img", { name: /illustration for page 1/i })).not.toBeInTheDocument();
  });
});
