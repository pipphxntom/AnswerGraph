/**
 * A2G - Ask to Governance UI JavaScript
 */
document.addEventListener('DOMContentLoaded', function() {
    // UI Elements
    const questionInput = document.getElementById('questionInput');
    const askButton = document.getElementById('askButton');
    const loader = document.getElementById('loader');
    const resultContainer = document.getElementById('resultContainer');
    const answerText = document.getElementById('answerText');
    const sourcesList = document.getElementById('sourcesList');
    const statsContainer = document.getElementById('statsContainer');
    const latencyValue = document.getElementById('latencyValue');

    // Function to handle the enter key
    questionInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            askQuestion();
        }
    });

    // Click handler for the ask button
    askButton.addEventListener('click', askQuestion);

    /**
     * Function to ask a question
     */
    function askQuestion() {
        const question = questionInput.value.trim();
        
        if (!question) {
            showError('Please enter a question');
            return;
        }
        
        // Show loader and hide previous results
        loader.style.display = 'block';
        resultContainer.classList.add('hidden');
        
        // Start timer for latency calculation
        const startTime = performance.now();
        
        // Make API request
        fetch('/api/v1/ask', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                text: question,
                lang: 'en'
            })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`API request failed with status ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            // Calculate latency
            const endTime = performance.now();
            const latency = endTime - startTime;
            
            // Force the loader to display for at least 2 seconds
            setTimeout(() => {
                displayResults(data, latency);
            }, Math.max(0, 2000 - latency));
        })
        .catch(error => {
            // Hide loader after at least 2 seconds
            setTimeout(() => {
                loader.style.display = 'none';
                showError('Error: ' + error.message);
                console.error('Error:', error);
            }, 2000);
        });
    }

    /**
     * Display the query results and sources
     */
    function displayResults(data, latency) {
        // Hide loader
        loader.style.display = 'none';
        
        // Display the answer
        answerText.textContent = data.text;
        
        // Display sources
        displaySources(data.sources);
        
        // Display stats if available
        if (statsContainer) {
            latencyValue.textContent = `${Math.round(latency)}ms`;
        }
        
        // Show the result container
        resultContainer.classList.remove('hidden');
    }

    /**
     * Display source citations
     */
    function displaySources(sources) {
        sourcesList.innerHTML = '';
        
        if (sources && sources.length > 0) {
            sources.forEach(source => {
                const sourceElement = document.createElement('div');
                sourceElement.className = 'source-item';
                
                let sourceText = '';
                if (source.name) {
                    sourceText += source.name;
                } else if (source.url) {
                    // Extract filename from URL
                    const urlParts = source.url.split('/');
                    sourceText += urlParts[urlParts.length - 1];
                }
                
                if (source.page) {
                    sourceText += ` (Page ${source.page})`;
                }
                
                // Create a clickable link if URL is provided
                if (source.url) {
                    const linkElement = document.createElement('a');
                    linkElement.href = source.url;
                    linkElement.textContent = sourceText;
                    linkElement.target = '_blank';
                    sourceElement.appendChild(linkElement);
                } else {
                    sourceElement.textContent = sourceText;
                }
                
                sourcesList.appendChild(sourceElement);
            });
        } else {
            sourcesList.innerHTML = '<p>No sources available</p>';
        }
    }

    /**
     * Show error message
     */
    function showError(message) {
        const errorElement = document.createElement('div');
        errorElement.className = 'error-message';
        errorElement.textContent = message;
        
        // Insert error before result container
        resultContainer.parentNode.insertBefore(errorElement, resultContainer);
        
        // Remove error after 5 seconds
        setTimeout(() => {
            if (errorElement.parentNode) {
                errorElement.parentNode.removeChild(errorElement);
            }
        }, 5000);
    }
});
