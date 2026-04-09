const TITLE_SORT_FIELD = "title";
const CREATED_SORT_FIELD = "created";

export const BOOK_SHELF_TAB = "bookshelf";
export const FAVORITES_TAB = "favorites";
export const ARCHIVE_TAB = "archive";

export const DEFAULT_SORT = {
  field: TITLE_SORT_FIELD,
  direction: "asc",
};

export const DEFAULT_SORTS_BY_TAB = {
  [BOOK_SHELF_TAB]: DEFAULT_SORT,
  [FAVORITES_TAB]: DEFAULT_SORT,
  [ARCHIVE_TAB]: DEFAULT_SORT,
};

const titleCollator = new Intl.Collator(undefined, {
  numeric: true,
  sensitivity: "base",
  ignorePunctuation: true,
});

const normalizeDirection = (direction) => (direction === "desc" ? "desc" : "asc");

const normalizeSort = (sort) => {
  if (!sort?.field) {
    return DEFAULT_SORT;
  }

  return {
    field: sort.field,
    direction: normalizeDirection(sort.direction),
  };
};

const parseCreatedAt = (value) => {
  if (value == null) {
    return null;
  }

  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }

  if (value instanceof Date) {
    const timestamp = value.getTime();
    return Number.isFinite(timestamp) ? timestamp : null;
  }

  const timestamp = Date.parse(value);
  return Number.isFinite(timestamp) ? timestamp : null;
};

const compareBookIds = (left, right) =>
  titleCollator.compare(String(left?.book_id ?? ""), String(right?.book_id ?? ""));

const compareTitles = (left, right) =>
  titleCollator.compare(String(left?.book_title ?? ""), String(right?.book_title ?? ""));

const compareCreatedAt = (left, right) => {
  const leftCreatedAt = parseCreatedAt(left?.created_at);
  const rightCreatedAt = parseCreatedAt(right?.created_at);

  if (leftCreatedAt == null && rightCreatedAt == null) {
    return compareBookIds(left, right);
  }

  if (leftCreatedAt == null) {
    return 1;
  }

  if (rightCreatedAt == null) {
    return -1;
  }

  if (leftCreatedAt !== rightCreatedAt) {
    return leftCreatedAt - rightCreatedAt;
  }

  return compareBookIds(left, right);
};

const reverseComparison = (comparison) => (comparison === 0 ? 0 : -comparison);

export const sortBooks = (books = [], sort = DEFAULT_SORT) => {
  const resolvedSort = normalizeSort(sort);

  return [...books].sort((left, right) => {
    let comparison;

    if (resolvedSort.field === CREATED_SORT_FIELD) {
      comparison = compareCreatedAt(left, right);
    } else {
      comparison = compareTitles(left, right);
      if (comparison === 0) {
        comparison = compareBookIds(left, right);
      }
    }

    return resolvedSort.direction === "desc" ? reverseComparison(comparison) : comparison;
  });
};

export const cycleSort = (currentSort, field) => {
  const resolvedSort = normalizeSort(currentSort);

  if (field === TITLE_SORT_FIELD) {
    if (resolvedSort.field === TITLE_SORT_FIELD) {
      return resolvedSort.direction === "asc"
        ? { field: TITLE_SORT_FIELD, direction: "desc" }
        : DEFAULT_SORT;
    }

    return DEFAULT_SORT;
  }

  if (field === CREATED_SORT_FIELD) {
    if (resolvedSort.field === CREATED_SORT_FIELD) {
      return resolvedSort.direction === "asc"
        ? { field: CREATED_SORT_FIELD, direction: "desc" }
        : DEFAULT_SORT;
    }

    return { field: CREATED_SORT_FIELD, direction: "asc" };
  }

  return DEFAULT_SORT;
};

export const getSortIcon = (sort, field) => {
  const resolvedSort = normalizeSort(sort);
  if (resolvedSort.field !== field) {
    return "swap_vert";
  }

  return resolvedSort.direction === "desc" ? "arrow_downward" : "arrow_upward";
};

export const isSortActive = (sort, field) => normalizeSort(sort).field === field;

export const SORT_FIELDS = {
  TITLE: TITLE_SORT_FIELD,
  CREATED: CREATED_SORT_FIELD,
};
