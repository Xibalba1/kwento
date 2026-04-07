// kwento/frontend/src/components/ThemeInput.js

import React, { useState, useEffect, useRef } from "react";

const ThemeInput = ({
  theme,
  setTheme,
  onSubmit,
  loading,
}) => {
  const [sparks, setSparks] = useState([]);
  const sparkIdRef = useRef(0); // To generate unique IDs for sparks

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit();
  };

  // Function to get a random vibrant color
  const getRandomColor = () => {
    const colors = [
      "#FF69B4", // Hot Pink
      "#00FFFF", // Aqua
      "#FFFF00", // Yellow
      "#FF4500", // OrangeRed
      "#8A2BE2", // BlueViolet
      "#00FF7F", // SpringGreen
      "#FF1493", // DeepPink
      "#1E90FF", // DodgerBlue
      "#32CD32", // LimeGreen
      "#FF6347", // Tomato
    ];
    return colors[Math.floor(Math.random() * colors.length)];
  };

  // Function to get a random shape
  const getRandomShape = () => {
    const shapes = ["circle", "star", "triangle"];
    return shapes[Math.floor(Math.random() * shapes.length)];
  };

  // Effect to handle continuous spark generation while loading
  useEffect(() => {
    let interval = null;
    if (loading) {
      const addSpark = () => {
        const id = sparkIdRef.current++;
        const angle = Math.random() * 360; // Random direction
        const distance = Math.random() * 30 + 20; // Random distance between 20px and 50px
        const duration = Math.random() * 0.5 + 0.5; // Random duration between 0.5s and 1s
        const color = getRandomColor();
        const shape = getRandomShape();

        const newSpark = {
          id,
          angle,
          distance,
          duration,
          color,
          shape,
        };

        setSparks((prev) => [...prev, newSpark]);

        // Remove the spark after its animation duration
        setTimeout(() => {
          setSparks((prev) => prev.filter((spark) => spark.id !== id));
        }, duration * 1000);
      };

      // Add a spark every 300ms
      interval = setInterval(() => {
        addSpark();
      }, 300);
    } else {
      setSparks([]); // Clear all sparks when not loading
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [loading]);

  return (
    <div>
      {/* Inline styles for animations */}
      <style>
        {`
          /* Pulsing Animation */
          @keyframes pulse {
            0% {
              transform: scale(1);
            }
            50% {
              transform: scale(1.05);
            }
            100% {
              transform: scale(1);
            }
          }

          /* Rainbow Color Cycling */
          @keyframes rainbow {
            0% { background-color: #ff0000; }   /* Red */
            16% { background-color: #ff7f00; }  /* Orange */
            33% { background-color: #ffff00; }  /* Yellow */
            50% { background-color: #00ff00; }  /* Green */
            66% { background-color: #0000ff; }  /* Blue */
            83% { background-color: #4b0082; }  /* Indigo */
            100% { background-color: #8f00ff; } /* Violet */
          }

          /* Pulsing and Rainbow Animation for the Button */
          .generate-button.loading {
            animation: pulse 1.5s infinite, rainbow 6s infinite;
            position: relative;
            overflow: hidden;
          }

          .theme-input::placeholder {
            color: #6b7280;
          }

          .theme-input:disabled::placeholder {
            color: #7c8798;
          }

          /* Sparks Animation */
          @keyframes spark {
            from {
              opacity: 1;
              transform: translate(0, 0) scale(1);
            }
            to {
              opacity: 0;
              transform: translate(var(--tx), var(--ty)) scale(0.5);
            }
          }

          /* Spark Shapes */

          /* Circle Sparks */
          .spark.circle {
            border-radius: 50%;
          }

          /* Triangle Sparks */
          .spark.triangle {
            width: 0px;
            height: 0px;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-bottom: 10px solid var(--spark-color);
            background: none;
          }

          /* Star Sparks */
          .spark.star {
            position: absolute;
            width: 0px;
            height: 0px;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-bottom: 10px solid var(--spark-color);
            transform: rotate(35deg);
            /* Create the star by adding a pseudo-element */
          }

          .spark.star::before {
            content: '';
            position: absolute;
            top: -6px;
            left: -5px;
            width: 0px;
            height: 0px;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 10px solid var(--spark-color);
            transform: rotate(-70deg);
          }

          /* Common Spark Styles */
          .spark {
            position: absolute;
            opacity: 0;
            pointer-events: none;
            animation: spark var(--spark-duration) linear forwards;
          }
        `}
      </style>

      <form onSubmit={handleSubmit} style={styles.form}>
        <input
          type="text"
          value={theme}
          onChange={(e) => setTheme(e.target.value)}
          placeholder="Enter a theme for your book"
          required
          disabled={loading}
          className="theme-input"
          style={{
            ...styles.input,
            ...(loading ? styles.inputDisabled : {}),
          }}
        />
        <button
          type="submit"
          disabled={loading}
          className={loading ? "generate-button loading" : "generate-button"}
          style={{
            ...styles.generateButton,
            position: "relative",
            overflow: "hidden",
          }}
        >
          {/* Render spark elements */}
          {sparks.map((spark) => (
            <span
              key={spark.id}
              className={`spark ${spark.shape}`}
              style={{
                '--tx': `${spark.distance * Math.cos((spark.angle * Math.PI) / 180)}px`,
                '--ty': `${spark.distance * Math.sin((spark.angle * Math.PI) / 180)}px`,
                '--spark-color': spark.color,
                '--spark-duration': `${spark.duration}s`,
              }}
            ></span>
          ))}

          <span style={{ zIndex: 1, position: "relative" }}>
            {loading ? "Generating..." : "Generate Book"}
          </span>
        </button>
      </form>
    </div>
  );
};

const styles = {
  form: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: "20px",
    flexWrap: "wrap",
  },
  input: {
    padding: "10px",
    width: "300px",
    borderRadius: "4px",
    border: "1px solid #ccc",
    fontSize: "16px",
    marginBottom: "10px",
    boxShadow: "rgba(0, 0, 0, 0.25) 1.95px 1.95px 2.6px",
  },
  inputDisabled: {
    backgroundColor: "#E5E7EB",
    border: "1px solid #B8C0CC",
    color: "#4B5563",
    cursor: "not-allowed",
    opacity: 1,
  },
  generateButton: {
    padding: "10px 20px",
    marginLeft: "10px",
    backgroundColor: "#1B9AAA",
    color: "#fff",
    border: "none",
    borderRadius: "4px",
    fontSize: "16px",
    cursor: "pointer",
    transition: "background-color 0.2s",
    marginBottom: "10px",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    position: "relative",
    boxShadow: "rgba(0, 0, 0, 0.25) 1.95px 1.95px 2.6px",
  },
};

export default ThemeInput;
