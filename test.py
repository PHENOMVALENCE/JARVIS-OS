import requests


# Replace with your actual API key
api_key = '4e26f961f6a48965866c3845c22854152866c99e35b85046ddc7bc1bfd1483a0'

# Set up the parameters
params = {
'q': "What is the best bait to use to trap an Alaskan Wolf?",
'api_key': api_key
}

# Make the request to SerpApi
response = requests.get('https://serpapi.com/search.json', params=params)

# Check if the request was successful
if response.status_code == 200:
    # Parse the JSON response
    results = response.json()

    # Extract and print the snippets
    snippet_string = f"System results:\n"
    for idx, result in enumerate(results['organic_results'], start=1):
        snippet = result.get('snippet', 'No snippet available').replace("...", "")
        snippet_string += f"Snippet {idx}: {snippet}\n"
    print(snippet_string)
    
else:
    print('Error:', response.status_code)