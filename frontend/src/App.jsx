import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import ItemList from './components/ItemList';
import Crawl from './components/Crawl';
import './App.css';

function App() {
  return (
    <Router>
      <div className="app">
        <header className="app-header">
          <nav>
            <Link to="/" className="nav-link">Trang chủ</Link>
            <Link to="/crawl" className="nav-link">Crawl</Link>
          </nav>
        </header>
        <main>
          <Routes>
            <Route path="/" element={<ItemList />} />
            <Route path="/crawl" element={<Crawl />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
