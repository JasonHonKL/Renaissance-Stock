// web/static/js/app.js
document.addEventListener('DOMContentLoaded', function() {
    const symbolInput = document.getElementById('symbolInput');
    const analyzeBtn = document.getElementById('analyzeBtn');
    const searchResults = document.getElementById('searchResults');
    const loadingIndicator = document.getElementById('loadingIndicator');
    const errorMessage = document.getElementById('errorMessage');
    const reportContainer = document.getElementById('reportContainer');
    const reportTitle = document.getElementById('reportTitle');
    const reportTimestamp = document.getElementById('reportTimestamp');
    const reportContent = document.getElementById('reportContent');
    
    // Handle symbol search
    let searchTimeout;
    symbolInput.addEventListener('input', function() {
        clearTimeout(searchTimeout);
        const query = symbolInput.value.trim();
        
        if (query.length < 2) {
            searchResults.classList.add('d-none');
            return;
        }
        
        searchTimeout = setTimeout(() => {
            searchSymbol(query);
        }, 500);
    });
    
    // Handle click outside search results
    document.addEventListener('click', function(event) {
        if (!searchResults.contains(event.target) && event.target !== symbolInput) {
            searchResults.classList.add('d-none');
        }
    });
    
    // Handle analyze button click
    analyzeBtn.addEventListener('click', function() {
        const symbol = symbolInput.value.trim();
        if (symbol) {
            analyzeStock(symbol);
        } else {
            showError('Please enter a stock symbol');
        }
    });
    
    // Handle enter key in input
    symbolInput.addEventListener('keypress', function(event) {
        if (event.key === 'Enter') {
            const symbol = symbolInput.value.trim();
            if (symbol) {
                analyzeStock(symbol);
            } else {
                showError('Please enter a stock symbol');
            }
        }
    });
    
    // Function to search for symbols
    async function searchSymbol(query) {
        try {
            const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
            const data = await response.json();
            
            if (data.status === 'success' && data.data.length > 0) {
                displaySearchResults(data.data);
            } else {
                searchResults.classList.add('d-none');
            }
        } catch (error) {
            console.error('Error searching for symbol:', error);
            searchResults.classList.add('d-none');
        }
    }
    
    // Function to display search results
    function displaySearchResults(results) {
        searchResults.innerHTML = '';
        
        results.forEach(result => {
            const item = document.createElement('a');
            item.href = '#';
            item.className = 'list-group-item list-group-item-action';
            item.innerHTML = `<strong>${result.symbol}</strong> - ${result.name} (${result.region})`;
            
            item.addEventListener('click', function(event) {
                event.preventDefault();
                symbolInput.value = result.symbol;
                searchResults.classList.add('d-none');
            });
            
            searchResults.appendChild(item);
        });
        
        searchResults.classList.remove('d-none');
    }
    
    // Function to analyze a stock
    async function analyzeStock(symbol) {
        // Show loading indicator
        loadingIndicator.classList.remove('d-none');
        errorMessage.classList.add('d-none');
        reportContainer.classList.add('d-none');
        
        try {
            const response = await fetch('/api/analyze', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ symbol: symbol })
            });
            
            const data = await response.json();
            
            if (data.status === 'success') {
                displayReport(data.data);
            } else {
                showError(data.message || 'Failed to analyze stock');
            }
        } catch (error) {
            console.error('Error analyzing stock:', error);
            showError('An error occurred while analyzing the stock');
        } finally {
            loadingIndicator.classList.add('d-none');
        }
    }
    
    // Function to display the report
    function displayReport(data) {
        reportTitle.textContent = `${data.symbol} - ${data.company_name}`;
        
        // Format timestamp
        const timestamp = new Date(data.timestamp);
        reportTimestamp.textContent = `Generated on ${timestamp.toLocaleDateString()} at ${timestamp.toLocaleTimeString()}`;
        
        // Set report content - ensure we're only getting the HTML content
        let htmlContent = data.report.html_content;
        
        // If the content still contains markdown code blocks, extract just the HTML
        if (htmlContent.includes('```')) {
            const codeBlockMatch = htmlContent.match(/```(?:html)?\s*([\s\S]*?)\s*```/);
            if (codeBlockMatch && codeBlockMatch[1]) {
                htmlContent = codeBlockMatch[1].trim();
            }
        }
        
        reportContent.innerHTML = htmlContent;
        
        // Show report container
        reportContainer.classList.remove('d-none');
        
        // Scroll to report
        reportContainer.scrollIntoView({ behavior: 'smooth' });
    }
    
    // Function to show an error message
    function showError(message) {
        errorMessage.textContent = message;
        errorMessage.classList.remove('d-none');
        loadingIndicator.classList.add('d-none');
    }
});