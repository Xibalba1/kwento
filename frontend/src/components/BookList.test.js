import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import BookList from "./BookList";

const baseProps = {
  loading: false,
  error: false,
  onRetry: jest.fn(),
  onSelectBook: jest.fn(),
};

const renderBookList = (books) =>
  render(<BookList {...baseProps} books={books} />);

describe("BookList", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test("renders the tab bar with Book Shelf active by default", () => {
    renderBookList([
      {
        book_id: "book-1",
        book_title: "Default Shelf Book",
      },
    ]);

    expect(screen.getByRole("tab", { name: /book shelf/i })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: /archive/i })).toHaveAttribute("aria-selected", "false");
    expect(screen.getByRole("button", { name: /default shelf book/i })).toBeInTheDocument();
  });

  test("uses a shared label wrapper and consistent tab height for both tabs", () => {
    renderBookList([
      {
        book_id: "book-shared-label",
        book_title: "Shared Label Book",
      },
    ]);

    const shelfTab = screen.getByRole("tab", { name: /book shelf/i });
    const archiveTab = screen.getByRole("tab", { name: /archive/i });
    const shelfLabel = screen.getByText("Book Shelf");
    const archiveLabel = screen.getByText("Archive");

    expect(shelfLabel.tagName).toBe("SPAN");
    expect(archiveLabel.tagName).toBe("SPAN");
    expect(shelfTab).toContainElement(shelfLabel);
    expect(archiveTab).toContainElement(archiveLabel);
    expect(shelfTab).toHaveStyle({ display: "flex", alignItems: "center", justifyContent: "center" });
    expect(archiveTab).toHaveStyle({ display: "flex", alignItems: "center", justifyContent: "center" });
    expect(shelfTab.style.height).toBe("52px");
    expect(archiveTab.style.height).toBe("52px");
    expect(shelfLabel).toHaveStyle({ minHeight: "100%" });
    expect(archiveLabel).toHaveStyle({ minHeight: "100%" });
  });

  test("keeps a shared active-tab bridge without inactive-only label offsets", () => {
    renderBookList([
      {
        book_id: "book-bridge",
        book_title: "Bridge Book",
      },
    ]);

    const bridge = screen.getByTestId("active-tab-bridge");
    const shelfTab = screen.getByRole("tab", { name: /book shelf/i });
    const archiveTab = screen.getByRole("tab", { name: /archive/i });

    expect(bridge).toHaveStyle({ bottom: "-8px", height: "12px" });
    expect(shelfTab.style.transform).toBe("");
    expect(archiveTab.style.transform).toBe("");
    expect(shelfTab.style.top).toBe("");
    expect(archiveTab.style.top).toBe("");
    expect(screen.getByText("Book Shelf")).not.toHaveStyle({ transform: expect.any(String) });
    expect(screen.getByText("Archive")).not.toHaveStyle({ transform: expect.any(String) });
  });

  test("renders title and cover image inside the book button when cover_url is present", () => {
    renderBookList([
      {
        book_id: "book-2",
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

  test("renders title-only when no shelf cover URL is available", () => {
    renderBookList([
      {
        book_id: "book-3",
        book_title: "Title Only",
      },
    ]);

    expect(screen.getByText("Title Only")).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  test("hides the image when it fails to load", async () => {
    renderBookList([
      {
        book_id: "book-4",
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
          },
        ]}
        onSelectBook={onSelectBook}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /clickable cover/i }));

    expect(onSelectBook).toHaveBeenCalledWith("book-5");
  });

  test("switches to Archive and back to Book Shelf", () => {
    renderBookList([
      {
        book_id: "book-6",
        book_title: "Archive Toggle Book",
      },
    ]);

    fireEvent.click(screen.getByRole("tab", { name: /archive/i }));

    expect(screen.getByRole("tab", { name: /archive/i })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("Archive is empty")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /archive toggle book/i })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: /book shelf/i }));

    expect(screen.getByRole("tab", { name: /book shelf/i })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("button", { name: /archive toggle book/i })).toBeInTheDocument();
  });

  test("renders loading state inline with tabs visible", () => {
    render(<BookList {...baseProps} books={[]} loading />);

    expect(screen.getByRole("tab", { name: /book shelf/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /archive/i })).toBeInTheDocument();
    expect(screen.getByText("Loading books...")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /close modal/i })).not.toBeInTheDocument();
  });

  test("renders error state inline with tabs visible and retry action", () => {
    const onRetry = jest.fn();

    render(<BookList {...baseProps} books={[]} error onRetry={onRetry} />);

    expect(screen.getByRole("tab", { name: /book shelf/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /archive/i })).toBeInTheDocument();
    expect(screen.getByText("Error fetching books. Please try again later.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /retry/i }));

    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  test("sizes every book button to the tallest card in the grid", async () => {
    const originalGetBoundingClientRect = HTMLElement.prototype.getBoundingClientRect;

    HTMLElement.prototype.getBoundingClientRect = jest.fn(function mockRect() {
      if (this.tagName === "BUTTON" && this.getAttribute("role") !== "tab") {
        if (this.textContent.includes("Tall Book")) {
          return { width: 200, height: 320, top: 0, left: 0, right: 200, bottom: 320 };
        }

        return { width: 200, height: 180, top: 0, left: 0, right: 200, bottom: 180 };
      }

      return { width: 0, height: 0, top: 0, left: 0, right: 0, bottom: 0 };
    });

    renderBookList([
      {
        book_id: "book-7",
        book_title: "Short Book",
      },
      {
        book_id: "book-8",
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
