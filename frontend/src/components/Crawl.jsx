import React, { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import FilterDropdown from './FilterDropdown';
import '../styles/Crawl.css';

// --- Constants ---
const CRAWL_API_BASE_URL = `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api`;
const CRAWL_WS_URL = `${import.meta.env.VITE_WS_URL || 'ws://localhost:8000'}/ws/crawl-status`;

// Categories from chotot_categories.json - using actual IDs
const ALL_CATEGORIES = {
  // 1010: "Căn hộ/Chung cư",
  // 1020: "Nhà ở",
  // 1030: "Văn phòng, Mặt bằng kinh doanh",
  // 1040: "Đất",
  // 2050: "Xe tải, xe ben",
  // 2010: "Ô tô",
  // 2020: "Xe máy",
  2030: "Phụ tùng xe",
  // 2060: "Xe đạp",
  // 2080: "Phương tiện khác",
  2090: "Xe điện",
  3050: "Đồng hồ",
  // 3030: "Quần áo",
  3060: "Giày dép",
  3070: "Túi xách",
  // 3080: "Nước hoa",
  3090: "Phụ kiện thời trang khác",
  4050: "Thiết bị chơi game",
  // 4010: "Đồ sưu tầm, đồ cổ",
  4020: "Đồ thể thao, Dã ngoại",
  // 4040: "Nhạc cụ",
  4060: "Sở thích khác",
  // 4070: "Sách",
  //5020: "Tivi, Âm thanh",
  5010: "Điện thoại",
  5030: "Laptop",
  5040: "Máy tính bảng",
  5050: "Máy ảnh, Máy quay",
  5060: "Phụ kiện (Màn hình, Chuột...)",
  // 5070: "Máy tính để bàn",
  5080: "Linh kiện (RAM, Card...)",
  5090: "Thiết bị đeo thông minh",
  // 6020: "Dịch vụ",
  // 6030: "Du lịch",
  // 7010: "Đồ ăn, thực phẩm và các loại khác",
  // 8030: "Đồ chuyên dụng, Giống nuôi trồng",
  8010: "Đồ dùng văn phòng",
  // 9070: "Máy giặt",
  // 9030: "Tủ lạnh",
  //9060: "Máy lạnh, điều hoà",
  11010: "Mẹ và bé",
  // 12030: "Chim",
  // 12010: "Gà",
  // 12020: "Chó",
  12040: "Phụ kiện, Thức ăn, Dịch vụ",
  // 12050: "Mèo",
  // 12060: "Thú cưng khác",
  // 13010: "Việc làm",
  //14010: "Bếp, lò, đồ điện nhà bếp",
  //14020: "Dụng cụ nhà bếp",
  14030: "Giường, chăn ga gối nệm",
  14040: "Thiết bị vệ sinh, nhà tắm",
  14050: "Quạt",
  14060: "Đèn",
  14070: "Bàn ghế",
  // 14080: "Tủ, kệ gia đình",
  14090: "Cây cảnh, đồ trang trí",
  // 15030: "Dịch vụ sửa chữa & bảo dưỡng điện máy",
  // 15010: "Dịch vụ dọn dẹp nhà",
  // 15020: "Dịch vụ chuyển nhà",
  //15040: "Dịch vụ nhà cửa khác"
};

// Provinces from regions_and_areas.yml - using actual region IDs
const ALL_PROVINCES = {
  13: 'Hồ Chí Minh',
  12: 'Hà Nội',
  2: 'Đông Nam Bộ', // Bình Dương, Đồng Nai, Bà Rịa - Vũng Tàu, Tây Ninh, Bình Phước
  4: 'Đồng bằng sông Hồng', // Hải Phòng, Nam Định, Thái Bình, Hà Nam
  10: 'Đông Bắc', // Quảng Ninh, Bắc Giang, Thái Nguyên, Tuyên Quang, Lạng Sơn, Hà Giang, Cao Bằng, Bắc Kạn
  1: 'Bắc Bộ', // Bắc Ninh, Hải Dương, Vĩnh Phúc, Hưng Yên, Phú Thọ, Ninh Bình, Hòa Bình
  8: 'Bắc Trung Bộ', // Thanh Hóa, Nghệ An, Hà Tĩnh
  5: 'Đồng bằng sông Cửu Long', // Long An, Cần Thơ, Kiên Giang, Tiền Giang, An Giang, Đồng Tháp, Trà Vinh, Cà Mau, Vĩnh Long, Sóc Trăng, Bến Tre, Hậu Giang, Bạc Liêu
  3: 'Đà Nẵng & Quảng Nam', 
  7: 'Nam Trung Bộ', // Khánh Hòa, Quảng Ngãi, Bình Định, Bình Thuận, Phú Yên, Ninh Thuận
  9: 'Tây Nguyên', // Lâm Đồng, Đắk Lắk, Gia Lai, Đắk Nông, Kon Tum
  6: 'Trị Thiên & Quảng Bình', // Thừa Thiên Huế, Quảng Bình, Quảng Trị
  11: 'Tây Bắc' // Lào Cai, Sơn La, Yên Bái, Điện Biên, Lai Châu
};

const Crawl = () => {
  const [selectedCategories, setSelectedCategories] = useState(() => {
    // Lấy data từ localStorage, nếu không có thì trả về mảng rỗng []
    const saved = localStorage.getItem('savedCategories');
    return saved ? JSON.parse(saved) : [];
  });

  const [selectedProvinces, setSelectedProvinces] = useState(() => {
    // Lấy data từ localStorage, nếu không có thì trả về mảng rỗng []
    const saved = localStorage.getItem('savedProvinces');
    return saved ? JSON.parse(saved) : [];
  });

  // Lưu vào localStorage khi người dùng thay đổi lựa chọn
  useEffect(() => {
    localStorage.setItem('savedCategories', JSON.stringify(selectedCategories));
  }, [selectedCategories]);

  useEffect(() => {
    localStorage.setItem('savedProvinces', JSON.stringify(selectedProvinces));
  }, [selectedProvinces]);
  const [isCrawling, setIsCrawling] = useState(false);
  const [crawlStatus, setCrawlStatus] = useState({});
  const [overallStatus, setOverallStatus] = useState('Idle');
  const [totalRoutes, setTotalRoutes] = useState(0);
  const ws = useRef(null);

  const connectWebSocket = useCallback(() => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      console.log('WebSocket already open.');
      return;
    }

    ws.current = new WebSocket(CRAWL_WS_URL);

    ws.current.onopen = () => {
      console.log('WebSocket Connected');
    };

    ws.current.onclose = () => {
      console.log('WebSocket Disconnected');
    };

    ws.current.onerror = (error) => {
      console.error('WebSocket Error:', error);
    };

    ws.current.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        console.log('WebSocket Message:', message);

        switch (message.type) {
          case 'CRAWL_STARTING':
            setOverallStatus('Starting');
            setCrawlStatus({});
            setIsCrawling(true);
            break;
            
          case 'TOTAL_ROUTES':
            setTotalRoutes(message.count);
            setOverallStatus('Crawling');
            break;
            
          case 'WORKERS_STARTED':
            setCrawlStatus(prev => ({
              ...prev,
              'workers': {
                status: 'started',
                count: message.workerCount
              }
            }));
            break;
            
          case 'ROUTES_QUEUED':
            setCrawlStatus(prev => ({
              ...prev,
              'queue': {
                status: 'queued'
              }
            }));
            break;
            
          case 'CRAWL_PROGRESS':
            setCrawlStatus(prev => ({
              ...prev,
              'overall': {
                status: 'running',
                totalProcessed: message.totalProcessed || 0,
                totalSaved: message.totalSaved || 0
              },
              [`worker_${message.workerId}`]: {
                status: 'working',
                processed: message.processed,
                saved: message.saved
              }
            }));
            break;
            
          case 'ROUTE_COMPLETED':
            setCrawlStatus(prev => ({
              ...prev,
              [message.route]: {
                status: 'completed',
                time: message.time,
                workerId: message.workerId,
                success: true
              }
            }));
            break;
            
          case 'CRAWL_FINISHED':
             setOverallStatus(message.status === 'Stopped' ? 'Stopped' : 'Completed');
             setIsCrawling(false);
            setCrawlStatus(prev => ({
              ...prev,
              'final': {
                status: 'completed',
                totalSaved: message.totalSaved || 0,
                totalProcessed: message.totalProcessed || 0,
                workerStats: message.workerStats || {}
              }
            }));
            break;
            
           case 'CRAWL_ERROR':
             setOverallStatus('Error');
             setIsCrawling(false);
            setCrawlStatus(prev => ({
              ...prev,
              'error': {
                status: 'error',
                error: message.error
              }
            }));
             console.error("Crawl Error:", message.error);
             break;
            
          default:
            console.log('Unknown WebSocket message type:', message.type);
        }
      } catch (error) {
        console.error('Error processing WebSocket message:', error);
      }
    };
  }, []);

  useEffect(() => {
    // Hàm này sẽ gọi Backend để hỏi xem nó có đang cào không
    const checkCrawlStatus = async () => {
      try {
        const response = await axios.get(`${CRAWL_API_BASE_URL}/crawl/status`);
        if (response.data.is_running) {
          setIsCrawling(true);
          setOverallStatus('Crawling (Restored)');
        }
      } catch (error) {
        console.error("Không thể lấy trạng thái Crawler từ Backend", error);
      }
    };
    
    checkCrawlStatus();
    connectWebSocket();
    
    return () => {
      ws.current?.close();
    };
  }, [connectWebSocket]);

  const startCrawling = async () => {
    if (isCrawling) return;
    try {
      setOverallStatus('Starting');
      setIsCrawling(true);
      setCrawlStatus({});
      setTotalRoutes(0);

      await axios.post(`${CRAWL_API_BASE_URL}/crawl`, {
        categories: selectedCategories.map(Number),
        provinces: selectedProvinces.map(Number),
      });
      console.log('Crawl request sent.');

    } catch (error) {
      const msg = error.response?.data?.detail || error.response?.data?.error || error.message;
      console.error('Error starting crawler:', msg);
      setOverallStatus('Error');
      setIsCrawling(false);
      setCrawlStatus({ error: { status: 'error', error: msg } });
    }
  };

  const stopCrawling = async () => {
    if (!isCrawling) return;
    try {
      setOverallStatus('Stopping');
      await axios.post(`${CRAWL_API_BASE_URL}/crawl/stop`);
      console.log('Stop request sent.');
    } catch (error) {
      console.error('Error stopping crawler:', error.response?.data?.detail || error.message);
      setOverallStatus('Error');
    }
  };

  const renderStatus = () => {
    const statusKeys = Object.keys(crawlStatus).sort();
    if (statusKeys.length === 0 && !isCrawling && overallStatus === 'Idle') {
      return <p>Select categories and provinces to start crawling.</p>;
    }
    if (overallStatus === 'Starting') return <p>Starting crawler...</p>;
    if (overallStatus === 'Stopping') return <p>Stopping crawler...</p>;

    const overallProgress = crawlStatus['overall'];
    const finalStats = crawlStatus['final'];
    const errorInfo = crawlStatus['error'];
    const workersInfo = crawlStatus['workers'];
    const queueInfo = crawlStatus['queue'];

    return (
      <div>
        <p>Overall Status: {overallStatus}</p>
        
        {workersInfo && (
          <div className="workers-info">
            <p><strong>Workers:</strong> {workersInfo.count} crawler workers started</p>
          </div>
        )}

        {queueInfo && (
          <div className="queue-info">
            <p><strong>Queue:</strong> Routes queued successfully</p>
          </div>
        )}
        
        {overallProgress && (
          <div className="overall-progress">
            <p><strong>Overall Progress:</strong> {overallProgress.totalProcessed || 0} routes processed, {overallProgress.totalSaved || 0} items saved</p>
          </div>
        )}

        {/* Worker Status */}
        {statusKeys.filter(key => key.startsWith('worker_')).length > 0 && (
          <div className="worker-status">
            <h4>Worker Status:</h4>
            <div className="worker-grid">
              {statusKeys
                .filter(key => key.startsWith('worker_'))
                .map(workerKey => {
                  const workerStatus = crawlStatus[workerKey];
                  const workerId = workerKey.replace('worker_', '');
                  return (
                    <div key={workerKey} className="worker-card">
                      <strong>Worker {workerId}:</strong> {workerStatus.processed} routes, {workerStatus.saved} items
                    </div>
                  );
                })}
            </div>
          </div>
        )}

        {/* Route Completions */}
        {statusKeys.filter(key => !['overall', 'final', 'error', 'workers', 'queue'].includes(key) && !key.startsWith('worker_')).length > 0 && (
          <div className="route-completions">
            <h4>Completed Routes:</h4>
        <ul className="crawl-status-list">
              {statusKeys
                .filter(key => !['overall', 'final', 'error', 'workers', 'queue'].includes(key) && !key.startsWith('worker_'))
                .map(route => {
                  const status = crawlStatus[route];
            return (
                    <li key={route} className={`status-${status.status}`}>
                      <strong>{route}:</strong>
                      {status.status === 'completed' && ` ✅ Completed in ${status.time}s (Worker ${status.workerId})`}
                {status.status === 'error' && ` ❌ Error: ${status.error || 'Unknown error'}`}
              </li>
            );
          })}
        </ul>
          </div>
        )}

        {finalStats && (
          <div className="final-stats">
            <p><strong>Final Results:</strong></p>
            <p>• Total Routes Processed: {finalStats.totalProcessed}</p>
            <p>• Total Items Saved: {finalStats.totalSaved}</p>
            {finalStats.workerStats && Object.keys(finalStats.workerStats).length > 0 && (
              <div className="worker-final-stats">
                <p><strong>Worker Statistics:</strong></p>
                {Object.entries(finalStats.workerStats).map(([workerId, stats]) => (
                  <p key={workerId}>
                    • Worker {workerId}: {stats.processed} routes, {stats.saved} items
                  </p>
                ))}
              </div>
            )}
          </div>
        )}

        {errorInfo && (
          <div className="error-info">
            <p><strong>Error:</strong> {errorInfo.error}</p>
          </div>
        )}

        {overallStatus === 'Completed' && <p className="success-message">All routes completed successfully!</p>}
        {overallStatus === 'Stopped' && <p className="warning-message">Crawling stopped by user.</p>}
        {overallStatus === 'Error' && <p className="error-message">Crawling finished with errors.</p>}
      </div>
    );
  };

  return (
    <div className="crawl-container">
      <div className="crawl-controls">
        <FilterDropdown
          label="Categories"
          options={ALL_CATEGORIES}
          selectedOptions={selectedCategories}
          onChange={setSelectedCategories}
          placeholder="Select Categories"
          isMultiSelect={true}
          disabled={isCrawling || overallStatus === 'Stopping'}
        />
        
        <FilterDropdown
          label="Provinces"
          options={ALL_PROVINCES}
          selectedOptions={selectedProvinces}
          onChange={setSelectedProvinces}
          placeholder="Select Provinces"
          isMultiSelect={true}
          disabled={isCrawling || overallStatus === 'Stopping'}
        />

        <div className="button-group">
          {!isCrawling ? (
            <button
              onClick={startCrawling}
              disabled={selectedCategories.length === 0 || selectedProvinces.length === 0 || overallStatus === 'Stopping'}
              className="start-button"
            >
              Start Crawling ({selectedCategories.length} categories × {selectedProvinces.length} provinces = {selectedCategories.length * selectedProvinces.length} routes)
            </button>
          ) : (
            <button
              onClick={stopCrawling}
              disabled={overallStatus === 'Stopping'}
              className="stop-button"
            >
              {overallStatus === 'Stopping' ? 'Stopping...' : 'Stop Crawling'}
            </button>
          )}
        </div>
      </div>

      <div className="progress-container">
        <h3>Crawling Status</h3>
        {renderStatus()}
      </div>
    </div>
  );
};

export default Crawl;