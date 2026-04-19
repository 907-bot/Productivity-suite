// Productivity OS - Global Configuration
const CONFIG = {
    // Change this to your hosted backend URL once deployed (e.g., https://prod-os-api.onrender.com)
    // Keep it empty or "http://localhost:8000" for local development
    BASE_URL: window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' 
              ? 'http://localhost' 
              : 'https://YOUR-BACKEND-URL.onrender.com', // <--- Update this after deployment!
    
    // API Mapping
    API: {
        LIFE: ':8001',
        WELLNESS: ':8002',
        FINANCE: ':8003',
        CONTENT: ':8004',
        RELATIONSHIP: ':8005'
    },
    
    // Production API Mapping (when consolidated)
    PROD_API: {
        LIFE: '/api/life',
        WELLNESS: '/api/wellness',
        FINANCE: '/api/finance',
        CONTENT: '/api/content',
        RELATIONSHIP: '/api/relationship'
    }
};

function getApiUrl(app) {
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
        return `http://localhost${CONFIG.API[app]}`;
    } else {
        return `${CONFIG.BASE_URL}${CONFIG.PROD_API[app]}`;
    }
}
