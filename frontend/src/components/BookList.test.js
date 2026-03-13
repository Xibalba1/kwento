import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import BookList from "./BookList";

const baseProps = {
  loading: false,
  error: false,
  onRetry: jest.fn(),
  onSelectBook: jest.fn(),
  onClose: jest.fn(),
};

const renderBookList = (books) =>
  render(<BookList {...baseProps} books={books} />);

describe("BookList", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test("renders title and cover image inside the book button when cover_url is present", () => {
    renderBookList([
      {
        book_id: "book-1",
        book_title: "The Cover Book",
        cover_url: "https://example.com/cover.png",
      },
    ]);

    const button = screen.getByRole("button", { name: /the cover book/i });
    expect(screen.getByText("The Cover Book")).toBeInTheDocument();

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

  test("renders title-only when cover_url is missing", () => {
    renderBookList([
      {
        book_id: "book-2",
        book_title: "Title Only",
      },
    ]);

    expect(screen.getByText("Title Only")).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  test("hides the image when it fails to load", async () => {
    renderBookList([
      {
        book_id: "book-3",
        book_title: "Broken Cover",
        cover_url: "https://example.com/broken-cover.png",
      },
    ]);

    const image = screen.getByRole("img", { name: /cover for broken cover/i });
    fireEvent.error(image);

    await waitFor(() => {
      expect(screen.queryByRole("img", { name: /cover for broken cover/i })).not.toBeInTheDocument();
    });
    expect(screen.getByText("Broken Cover")).toBeInTheDocument();
  });

  test("selects the book and closes the modal when clicked", () => {
    const onSelectBook = jest.fn();
    const onClose = jest.fn();

    render(
      <BookList
        {...baseProps}
        books={[
          {
            book_id: "book-4",
            book_title: "Clickable Cover",
            cover_url: "https://example.com/cover.png",
          },
        ]}
        onSelectBook={onSelectBook}
        onClose={onClose}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /clickable cover/i }));

    expect(onSelectBook).toHaveBeenCalledWith("book-4");
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  test("sizes every book button to the tallest card in the grid", async () => {
    const originalGetBoundingClientRect = HTMLElement.prototype.getBoundingClientRect;

    HTMLElement.prototype.getBoundingClientRect = jest.fn(function mockRect() {
      if (this.tagName === "BUTTON") {
        if (this.textContent.includes("Tall Book")) {
          return { width: 200, height: 320, top: 0, left: 0, right: 200, bottom: 320 };
        }

        return { width: 200, height: 180, top: 0, left: 0, right: 200, bottom: 180 };
      }

      return { width: 0, height: 0, top: 0, left: 0, right: 0, bottom: 0 };
    });

    renderBookList([
      {
        book_id: "book-5",
        book_title: "Short Book",
      },
      {
        book_id: "book-6",
        book_title: "Tall Book",
        cover_url: "https://example.com/tall-cover.png",
      },
    ]);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /short book/i }).style.height).toBe("320px");
      expect(screen.getByRole("button", { name: /tall book/i }).style.height).toBe("320px");
    });

    HTMLElement.prototype.getBoundingClientRect = originalGetBoundingClientRect;
  });
});
