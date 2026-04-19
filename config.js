// Productivity OS - Global Configuration
const CONFIG = {
    // Hosted backend URL on Render
    BASE_URL: window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' 
              ? 'http://localhost' 
              : 'https://productivity-suite-sror.onrender.com',
    
    // API Mapping (Local)
    API: {
        LIFE: ':8001',
        WELLNESS: ':8002',
        FINANCE: ':8003',
        CONTENT: ':8004',
        RELATIONSHIP: ':8005'
    },
    
    // Production API Mapping (Consolidated on Render)
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
