import { useState, useEffect } from 'react';
import Login from './Login';
import Documents from './Documents';
import Query from './Query';
import Analytics from './Analytics';
import './App.css';

function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (token) {
      setIsLoggedIn(true);
    }
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setIsLoggedIn(false);
  };

  if (!isLoggedIn) {
    return <Login onLoginSuccess={() => setIsLoggedIn(true)} />;
  }

  return (
    <div
      className="min-h-screen lg:h-screen flex flex-col lg:overflow-hidden"
      style={{ backgroundColor: "#F5F6FA" }}
    >
      <div
        className="flex items-center justify-between px-8 py-4 flex-shrink-0"
        style={{ backgroundColor: "#1B1E3D" }}
      >
        <h2
          className="text-xl font-semibold text-white"
          style={{ fontFamily: "'Lora', serif" }}
        >
          OmniRAG
        </h2>
        <button
          onClick={handleLogout}
          className="px-4 py-1.5 text-sm rounded-md font-medium transition-colors"
          style={{ backgroundColor: "rgba(255,255,255,0.1)", color: "#fff" }}
          onMouseEnter={(e) => (e.target.style.backgroundColor = "rgba(255,255,255,0.18)")}
          onMouseLeave={(e) => (e.target.style.backgroundColor = "rgba(255,255,255,0.1)")}
        >
          Log out
        </button>
      </div>
      <div className="flex-1 lg:min-h-0 grid grid-cols-1 lg:grid-cols-5 gap-6 p-6 lg:overflow-hidden">
        <div className="lg:col-span-3 lg:h-full lg:min-h-0">
          <Query />
        </div>
        <div className="lg:col-span-2 lg:h-full flex flex-col gap-6 lg:min-h-0">
          <div className="flex-shrink-0">
            <Analytics />
          </div>
          <div className="flex-1 lg:min-h-0">
            <Documents />
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;