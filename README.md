#Online Universities Downloader scripts
---

I use this scripts to download and store coursera resources (videos, subtitles and slides).

### Requisites
* Python2 (2.5 or newer, tested on Python 2.7 but i think i don't use features not found in 2.5, have to try)
* PyCurl (http://pycurl.sourceforge.net/ for windows use http://www.lfd.uci.edu/~gohlke/pythonlibs/#pycurl)
* lxml (in Pypi and http://lxml.de/index.html#download)

### Features

* Multi-platform (tested on Windows and Linux, i have to test yet in OSX).
* Use cookies from Chromium or Firefox, in Linux use Chromium cookies path by default
* Course selected from command line.
* Only download what's new, check the existence of files in the output folder before download them.
* Select what to download from videos, subtitles, slides.
* Select in what format do you want the subtitles and slides.
* Limits download speed.
* Search for a concrete section in the selected course.
* Log activity
* Let's you stop download using ctrl+c
* Show a progress bar in console
* Rename resources to be the same of the lesson title, and create the sections directories for you.
* Autonumerate videos and sections to let you know the original order found in the course.

### Help output
    Usage: coursera_downloader.py [options]

    Options:
      -h, --help            show this help message and exit
      -x, --verbose         verbose print log messages to console, default: False
      -c COURSE, --course=COURSE
			    the course url path inside www.coursera.org examples:
			    saas, modelthinking, algo, nlp, crypto, pgm,
			    gametheory
      -o OUTPUT_FOLDER, --output-folder=OUTPUT_FOLDER
			    the folder where we will store and sync our downloads
      -b COOKIES_BROWSER, --cookies-browser=COOKIES_BROWSER
			    the browser from where we are going to read the needed
			    cookies, default: chromium, options: firefox, chromium
      -k COOKIES_DB_PATH, --cookies-db-path=COOKIES_DB_PATH
			    the path for the selected browser sqlite cookies
			    storage file, default:
			    /home/USER/.config/chromium/Default/Cookies
      -v, --download-videos
			    download selected course videos, default: False
      -s, --download-subtitles
			    download selected course subtitles, default: False
      -f SUBTITLES_FORMAT, --subtitles-format=SUBTITLES_FORMAT
			    the format for the subtitles to download: txt, srt,
			    default: srt
      -i, --download-slides
			    download selected course slides (links in videos
			    page), default: False
      -p SLIDES_FORMAT, --slides-format=SLIDES_FORMAT
			    the format for the slides to download: pptx, ppt, pdf,
			    default: pdf
      -m MAX_BANDWITH, --max-bandwith=MAX_BANDWITH
			    maximum bandwith to use in downloads in bytes/s,
			    default: None
      -r SEARCH_STRING_SECTION, --search-string-section=SEARCH_STRING_SECTION
			    let's specify a search string to download only the
			    section that have this text in his name
      -d, --disable-progressbar
			    disable the progress bar shown downloading files

### Usage examples
Download nlp class videos and subtitles in srt format to /tmp/nlp at a maximum rate of 250Kb/s using the default Chromium cookies in Linux.

    ./coursera_downloader.py -c nlp -o /tmp/nlp -v -s -f srt -m 250000

Download algo class slides in pdf format to /tmp/algo using cookies from Firefox in Linux without maximum rate.

    ./coursera_downloader.py -c algo -o /tmp/algo -i -p pdf -b firefox -k ~/.mozilla/firefox/174o50qz.default/cookies.sqlite

Download all the content from ModelThinking to c:\temp\modelthinking class in Windows 7 using Chrome cookies.

    coursera_downloader.py -c modelthinking -o c:\temp\modelthinking -v -i -s -k c:\users\USER\AppData\Local\Google\Chrome\User Data\Default\Cookies

### Know bugs
* In windows i can't use the cookies from Firefox if it is 4 or newer, they changed sqlite to use a feature in cookies.sqlite only available to sqlite 3.7.0 or newer but sqlite bundled in python it is 3.6.2, i didn't have time to research if i can do any workaround.

### FAQ
#####Why?
* I think this videos are gold, i am doing all the courses that i can and i am storing the videos for future reference, last fall i did Machine Learning and databases and still any times i consult the videos i downloaded at the time.
* I use chromium in Linux and i have not found a good way to rate-limit the download so when i am downloading content manually i am efectively consuming all my bandwith, i have used trickle other times or QoS but anyway i would have to manually download every link and rename to the lesson title every resource manually this is just better.

### TODO
* Add default paths for cookies, Firefox in Linux and Windows and Chrome in Windows.
* Create an self-contained exe with Pyinstaller for Windows users.
