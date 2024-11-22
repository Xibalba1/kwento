import React, { useEffect, useState } from 'react';

const BookList = ({ onSelectBook }) => {
  const [books, setBooks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    const fetchBooks = async () => {
      try {
        const response = await fetch('http://localhost:8000/books/', {
          method: 'GET',
          headers: { 'Content-Type': 'application/json' },
        });
        if (!response.ok) {
          throw new Error('Failed to fetch books');
        }
        const data = await response.json();
        setBooks(data);
      } catch (error) {
        console.error(error);
        setError(true);
      } finally {
        setLoading(false);
      }
    };

    fetchBooks();
  }, []);

  if (loading) {
    return <p style={styles.message}>Loading books...</p>;
  }

  if (error) {
    return <p style={styles.message}>Error fetching books. Please try again later.</p>;
  }

  if (books.length === 0) {
    return <p style={styles.message}>No books available.</p>;
  }

  return (
    <div style={styles.listContainer}>
      <h2>Available Books</h2>
      <ul style={styles.list}>
        {books.map((book) => (
          <li key={book.book_id} style={styles.listItem}>
            <button
            style={styles.button}
            onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#3700B3')}
            onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = '#6200EE')}
            onClick={() => onSelectBook(book.book_id)}
            >
            {book.title}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
};

const styles = {
    listContainer: {
      textAlign: 'center',
      marginTop: '20px',
    },
    list: {
      listStyleType: 'none',
      padding: 0,
      margin: '0 auto',
      maxWidth: '400px',
    },
    listItem: {
      marginBottom: '10px',
    },
    button: {
      width: '100%',
      padding: '15px',
      fontSize: '18px',
      color: '#fff',
      backgroundColor: '#6200EE',
      border: 'none',
      borderRadius: '8px',
      cursor: 'pointer',
      textAlign: 'left',
      boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)',
      transition: 'background-color 0.2s ease',
    },
    buttonHover: {
      backgroundColor: '#3700B3',
    },
    message: {
      textAlign: 'center',
      marginTop: '20px',
    },
  };
  
export default BookList;