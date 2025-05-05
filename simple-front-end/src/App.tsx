import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion'; // For result animations

// --- Shadcn UI Imports ---
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Separator } from '@/components/ui/separator';
// import { Pagination, PaginationContent, PaginationEllipsis, PaginationItem, PaginationLink, PaginationNext, PaginationPrevious } from '@/components/ui/pagination';
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

import  axios  from "axios";

// --- Icons (lucide-react) ---
import { Upload, FileAudio, Link as LinkIcon, Image as ImageIcon, Search, Loader2, CheckCircle, AlertCircle, Mic } from 'lucide-react';

// --- Types ---
interface ApiSearchResult {
  page_url: string;
  similarity: number; 
  media_type: 'image' | 'audio';
}

interface SearchResultDisplay {
  id: string; // Generate client-side
  pageUrl: string;
  previewType: 'image' | 'audio';
  similarity: number; // Store as 0-1 or percentage? API returns 0-1 like value (1-distance)
  // Add preview URL generation logic if needed
  previewUrl: string;
}

const API_BASE_URL = '/api/v1';

function App() {
  // --- State ---
  const [activeTab, setActiveTab] = useState('image');
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [urlInput, setUrlInput] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResultDisplay[]>([]);
  const [isLoading, setIsLoading] = useState(false); // General loading for search
  const [isScraping, setIsScraping] = useState(false); // Specific loading for URL scrape
  const [scrapeSuccess, setScrapeSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false); // For drag-and-drop visual feedback


  // --- Handlers ---

  const handleFileChange = (
    event: React.ChangeEvent<HTMLInputElement>,
    type: 'image' | 'audio'
  ) => {
    setError(null); // Clear previous errors
    const file = event.target.files?.[0];
    if (file) {
      const expectedPrefix = type === 'image' ? 'image/' : 'audio/';
      if (file.type.startsWith(expectedPrefix)) {
        if (type === 'image') setImageFile(file);
        else setAudioFile(file);
      } else {
        setError(`Invalid file type. Please upload a${type === 'image' ? 'n image' : ' audio'} file.`);
        if (type === 'image') setImageFile(null);
        else setAudioFile(null);
      }
    }
     // Reset input value to allow re-uploading the same file
     event.target.value = '';
  };

  const handleDrop = (
    event: React.DragEvent<HTMLDivElement>,
    type: 'image' | 'audio'
  ) => {
    event.preventDefault();
    event.stopPropagation();
    setError(null);
    setDragOver(false);
    const file = event.dataTransfer.files?.[0];
    if (file) {
      const expectedPrefix = type === 'image' ? 'image/' : 'audio/';
       if (file.type.startsWith(expectedPrefix)) {
        if (type === 'image') setImageFile(file);
        else setAudioFile(file);
      } else {
        setError(`Invalid file type. Please drop a${type === 'image' ? 'n image' : ' audio'} file.`);
         if (type === 'image') setImageFile(null);
         else setAudioFile(null);
      }
    }
  };

  const handleDragOver = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    setDragOver(true);
  };

  const handleDragLeave = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    setDragOver(false);
  };

  const handleSearch = async (type: 'image' | 'audio') => {
    const fileToSearch = type === 'image' ? imageFile : audioFile;
    if (!fileToSearch) {
      setError(`No ${type} file selected.`);
      return;
    }

    setError(null);
    setScrapeSuccess(null);
    setSearchResults([]); 
    setIsLoading(true);

    console.log(`Searching with ${type}:`, fileToSearch.name);

    // Create FormData
    const formData = new FormData();
    formData.append('media_file', fileToSearch); // Field name must match Go handler

    console.log(formData)

    try {
      // Make API call (adjust API_BASE_URL if not using proxy)
      const response = await axios.post<{ results: ApiSearchResult[] }>(
          `${API_BASE_URL}/search`, 
          formData, 
          { 
              headers: { 'Content-Type': 'multipart/form-data' } 
          }
      );

      console.log(response)

      // Map API results to display results
      const displayResults = response.data.results.map((res, index): SearchResultDisplay => {
        // Basic client-side ID generation
        const id = `result-${Date.now()}-${index}`; 
        // Generate a simple preview placeholder or link
        const previewUrl = res.media_type === 'image'
            ? `https://via.placeholder.com/100x60.png?text=Preview` // Replace with better placeholder or logic
            : `https://via.placeholder.com/100x60.png?text=Audio`;

        return {
            id: id,
            pageUrl: res.page_url,
            similarity: Math.round(res.similarity * 100), // Convert 0-1 to percentage
            previewType: res.media_type,
            previewUrl: previewUrl, // Use generated/placeholder preview
        };
      });
      
      // Sort by similarity descending (API might already do this)
      displayResults.sort((a, b) => b.similarity - a.similarity);

      setSearchResults(displayResults);

    } catch (err: any) {
      console.error("Search API error:", err);
      let errorMsg = `Failed to perform ${type} search.`;
      if (axios.isAxiosError(err) && err.response?.data?.error) {
        errorMsg = `Search failed: ${err.response.data.error}`;
      } else if (err instanceof Error) {
        errorMsg = `Search failed: ${err.message}`;
      }
      setError(errorMsg);
      setSearchResults([]); // Clear results on error
    } finally {
      setIsLoading(false);
    }
  };

  const handleUrlScrape = async () => {
    setError(null);
    setScrapeSuccess(null);
    setSearchResults([]); 

    try {
      new URL(urlInput); 
    } catch (_) {
      setError("Invalid URL format.");
      return;
    }

    setIsScraping(true);
    console.log("Requesting scrape for URL:", urlInput);

    try {
        // Prepare payload (only URL for now, add others if needed)
        const payload = {
            url: urlInput,
            depth_limit: 1, // Example: Send parameters if API supports them
            use_playwright: false 
        };

        // Make API call (adjust API_BASE_URL if not using proxy)
        const response = await axios.post<{ job_id: string, status: string, message: string }>(
            `${API_BASE_URL}/scrape`, 
            payload
        );

        console.log(response)

        if (response.data.status === 'ACCEPTED') {
            setScrapeSuccess(`Scrape job accepted (ID: ${response.data.job_id}). Processing initiated.`);
        } else {
             setError(`Scrape job rejected: ${response.data.message || 'Unknown reason'}`);
        }

    } catch (err: any) {
         console.error("Scrape API error:", err);
        let errorMsg = "Failed to initiate scrape.";
        if (axios.isAxiosError(err) && err.response?.data?.error) {
            errorMsg = `Scrape initiation failed: ${err.response.data.error}`;
        } else if (axios.isAxiosError(err) && err.response?.data?.message) {
             errorMsg = `Scrape initiation failed: ${err.response.data.message}`;
        } else if (err instanceof Error) {
            errorMsg = `Scrape initiation failed: ${err.message}`;
        }
        setError(errorMsg);
    } finally {
      setIsScraping(false);
    }
  };

  // --- Render Helper for File Input ---
  const renderFileInput = (
    type: 'image' | 'audio',
    file: File | null,
    setFile: (file: File | null) => void,
    accept: string
  ) => (
    <div className="space-y-4">
       {/* Drag and Drop Area */}
       <div
        className={`flex flex-col items-center justify-center w-full h-32 border-2 border-dashed rounded-lg cursor-pointer bg-muted/40 hover:bg-muted/60 transition-colors
                    ${dragOver ? 'border-primary' : 'border-border'}`}
        onDrop={(e) => handleDrop(e, type)}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => document.getElementById(`${type}-file-input`)?.click()} // Trigger hidden input on click
      >
        <div className="flex flex-col items-center justify-center pt-5 pb-6 text-center">
          <Upload className="w-8 h-8 mb-2 text-muted-foreground" />
          <p className="mb-1 text-sm text-muted-foreground">
            <span className="font-semibold">Click to upload</span> or drag and drop
          </p>
          <p className="text-xs text-muted-foreground">
            {type === 'image' ? 'PNG, JPG, GIF, WEBP etc.' : 'MP3, WAV, OGG etc.'}
          </p>
        </div>
      </div>

      {/* Hidden Actual File Input */}
      <Input
        id={`${type}-file-input`}
        type="file"
        className="hidden"
        accept={accept}
        onChange={(e) => handleFileChange(e, type)}
      />

      {/* Display Selected File */}
      {file && (
        <div className="text-sm text-muted-foreground flex items-center justify-center gap-2">
          Selected: <span className="font-medium text-foreground truncate max-w-[200px]">{file.name}</span>
          <Button variant="ghost" size="sm" className="h-6 px-1.5 text-red-500 hover:text-red-600" onClick={() => setFile(null)}>
             <AlertCircle className="w-4 h-4" />
          </Button>
        </div>
      )}

      {/* Go Button */}
      <Button
        className="w-full"
        onClick={() => handleSearch(type)}
        disabled={!file || isLoading}
      >
        {isLoading ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        ) : (
            <Search className="mr-2 h-4 w-4" />
        )}
        Go
      </Button>
    </div>
  );


  // --- Render Helper for Search Results ---
  const renderResults = () => {
    if (isLoading) {
      return (
        <div className="flex justify-center items-center p-10">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="ml-3 text-muted-foreground">Searching...</p>
        </div>
      );
    }

    if (searchResults.length === 0) {
       // Don't show anything if no search has been performed yet,
       // unless there's an error or success message from scraping
       if (!error && !scrapeSuccess && !isScraping) return null;
       // Keep space for potential error/success messages below
       return <div className="h-10"></div>;
    }

    const topResults = searchResults.slice(0, 10);
    const otherResults = searchResults.slice(10);

    const cardVariants = {
        hidden: { opacity: 0, y: 20 },
        visible: (i: number) => ({
            opacity: 1,
            y: 0,
            transition: {
                delay: i * 0.05, // Stagger animation
                duration: 0.3
            },
        }),
    };

    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.5 }}
        className="mt-8 w-full max-w-4xl" // Limit width of results section
      >
        <Card>
          <CardHeader>
            <CardTitle>Search Results ({searchResults.length})</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Top 10 Results */}
            <div>
              <h3 className="text-lg font-semibold mb-3">Top Matches</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {topResults.map((result, index) => (
                  <motion.div
                    key={result.id}
                    custom={index}
                    initial="hidden"
                    animate="visible"
                    variants={cardVariants}
                  >
                    <Card className="overflow-hidden h-full flex flex-col">
                      <CardContent className="p-4 flex-grow">
                        <div className="aspect-video bg-muted rounded-md mb-3 overflow-hidden flex items-center justify-center">
                          {result.previewType === 'image' ? (
                            <img
                              src={result.previewUrl}
                              alt="Result preview"
                              className="object-cover w-full h-full"
                            />
                          ) : (
                             <div className="text-center p-2">
                                <FileAudio className="w-8 h-8 mx-auto text-muted-foreground mb-1"/>
                                <p className="text-xs text-muted-foreground">Audio Preview</p>
                            </div>
                          )}
                        </div>
                        <a
                          href={result.previewUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm font-medium text-blue-600 hover:underline break-all line-clamp-2"
                        >
                          {result.pageUrl}
                        </a>
                      </CardContent>
                      <div className="bg-muted/50 px-4 py-2 border-t text-sm font-medium text-right">
                         Match: <span className="text-primary">{result.similarity}%</span>
                      </div>
                    </Card>
                   </motion.div>
                ))}
              </div>
            </div>

            {/* Separator and Other Results */}
            {otherResults.length > 0 && (
              <>
                <Separator />
                <div>
                  <h3 className="text-lg font-semibold mb-3">Other Results</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {otherResults.map((result, index) => (
                       <motion.div
                            key={result.id}
                            custom={index + topResults.length} // Adjust delay index
                            initial="hidden"
                            animate="visible"
                            variants={cardVariants}
                       >
                        <Card className="overflow-hidden h-full flex flex-col">
                         <CardContent className="p-4 flex-grow">
                           <div className="aspect-video bg-muted rounded-md mb-3 overflow-hidden flex items-center justify-center">
                             {result.previewType === 'image' ? (
                               <img
                                 src={result.previewUrl}
                                 alt="Result preview"
                                 className="object-cover w-full h-full"
                               />
                             ) : (
                                <div className="text-center p-2">
                                    <FileAudio className="w-8 h-8 mx-auto text-muted-foreground mb-1"/>
                                    <p className="text-xs text-muted-foreground">Audio Preview</p>
                                </div>
                             )}
                           </div>
                           <a
                             href={result.previewUrl}
                             target="_blank"
                             rel="noopener noreferrer"
                             className="text-sm font-medium text-blue-600 hover:underline break-all line-clamp-2"
                           >
                             {result.pageUrl}
                           </a>
                         </CardContent>
                         <div className="bg-muted/50 px-4 py-2 border-t text-sm font-medium text-right">
                            Match: <span className="text-primary">{result.similarity}%</span>
                         </div>
                        </Card>
                       </motion.div>
                    ))}
                  </div>
                </div>
              </>
            )}

            {/* Placeholder Pagination */}
            {/* {searchResults.length > 10 && ( // Only show if there are enough results to paginate
                <div className="pt-6">
                    <Pagination>
                        <PaginationContent>
                        <PaginationItem>
                            <PaginationPrevious href="#" className="pointer-events-none opacity-50" />
                        </PaginationItem>
                        <PaginationItem>
                            <PaginationLink href="#" isActive>1</PaginationLink>
                        </PaginationItem>
                        <PaginationItem>
                             <PaginationLink href="#">2</PaginationLink>
                        </PaginationItem>
                         <PaginationItem>
                            <PaginationEllipsis />
                         </PaginationItem>
                        <PaginationItem>
                            <PaginationNext href="#" />
                        </PaginationItem>
                        </PaginationContent>
                    </Pagination>
                 </div>
            )} */}
          </CardContent>
        </Card>
      </motion.div>
    );
  };


  // --- Main Component Return ---
  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col items-center justify-center p-4 lg:p-8">
      <h1 className="text-3xl font-bold mb-8 text-center">Media Search</h1>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full max-w-xl">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="image">
             <ImageIcon className="w-4 h-4 mr-2" /> Image
          </TabsTrigger>
          <TabsTrigger value="audio">
              <FileAudio className="w-4 h-4 mr-2" /> Audio
          </TabsTrigger>
          <TabsTrigger value="url">
              <LinkIcon className="w-4 h-4 mr-2" /> URL
          </TabsTrigger>
        </TabsList>

        {/* --- Image Tab --- */}
        <TabsContent value="image">
          <Card>
            <CardHeader>
              <CardTitle>Image Search</CardTitle>
              <CardDescription>Upload or drop an image file to find similar media.</CardDescription>
            </CardHeader>
            <CardContent>
              {renderFileInput('image', imageFile, setImageFile, 'image/*')}
            </CardContent>
          </Card>
        </TabsContent>

        {/* --- Audio Tab --- */}
        <TabsContent value="audio">
          <Card>
            <CardHeader>
              <CardTitle>Audio Search</CardTitle>
              <CardDescription>Upload an audio file or record audio to find similar media.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Placeholder Recording Button */}
               <Button variant="outline" className="w-full" disabled>
                   <Mic className="mr-2 h-4 w-4" /> Start Recording (Placeholder)
               </Button>
              {renderFileInput('audio', audioFile, setAudioFile, 'audio/*')}
            </CardContent>
          </Card>
        </TabsContent>

        {/* --- URL Tab --- */}
        <TabsContent value="url">
          <Card>
            <CardHeader>
              <CardTitle>URL Processing</CardTitle>
              <CardDescription>Enter a URL to process its content (e.g., scrape for media).</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="url-input">Media URL</Label>
                <Input
                  id="url-input"
                  type="url" // Basic browser validation
                  placeholder="https://example.com/image.jpg"
                  value={urlInput}
                  onChange={(e) => setUrlInput(e.target.value)}
                  disabled={isScraping}
                />
              </div>
              <Button
                className="w-full"
                onClick={handleUrlScrape}
                disabled={!urlInput || isScraping}
              >
                {isScraping ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                    <Search className="mr-2 h-4 w-4" /> // Or a different icon like Play or Send
                )}
                 {isScraping ? 'Processing...' : 'Scrape'}
              </Button>

               {/* Scraping Feedback */}
               <AnimatePresence>
                    {isScraping && (
                        <motion.div
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: 'auto' }}
                            exit={{ opacity: 0, height: 0 }}
                            className="flex items-center justify-center text-sm text-muted-foreground pt-2"
                        >
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            Processing URL... please wait.
                        </motion.div>
                    )}
                    {scrapeSuccess && (
                         <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                            <Alert variant="default" className="mt-4 bg-green-50 border border-green-200">
                                <CheckCircle className="h-4 w-4 text-green-600" />
                                <AlertTitle className="text-green-800">Success</AlertTitle>
                                <AlertDescription className="text-green-700">
                                    {scrapeSuccess}
                                </AlertDescription>
                            </Alert>
                        </motion.div>
                    )}
                </AnimatePresence>

            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

       {/* --- General Error Display Area (Below Tabs) --- */}
       <AnimatePresence>
        {error && (
             <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 10 }}
                className="w-full max-w-xl mt-4"
            >
                <Alert variant="destructive">
                    <AlertCircle className="h-4 w-4" />
                    <AlertTitle>Error</AlertTitle>
                    <AlertDescription>{error}</AlertDescription>
                </Alert>
            </motion.div>
        )}
      </AnimatePresence>


      {/* --- Results Section --- */}
       <AnimatePresence>
         {renderResults()}
       </AnimatePresence>

    </div>
  );
}

export default App;