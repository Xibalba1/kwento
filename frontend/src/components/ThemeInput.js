import React from "react";

const ThemeInput = ({ theme, setTheme, onSubmit, loading }) => {
  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit();
  };

  return (
    <form onSubmit={handleSubmit} style={{ marginBottom: "20px" }}>
      <input
        type="text"
        value={theme}
        onChange={(e) => setTheme(e.target.value)}
        placeholder="Enter a theme for your book"
        required
        style={{ padding: "10px", width: "300px" }}
      />
      <button type="submit" disabled={loading} style={{ padding: "10px", marginLeft: "10px" }}>
        {loading ? "Generating..." : "Generate Book"}
      </button>
    </form>
  );
};

export default ThemeInput;
