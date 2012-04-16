#!/usr/bin/env python2
# -*- coding: utf-8 -*-
import sys, logging, logging.handlers, cookielib, os, urllib2, re, signal, functools
from cStringIO import StringIO
from itertools import izip
from optparse import OptionParser

#3rd party modules
def exit_module_not_found(module):
    print 'This program requires %s' % module
    sys.exit(1)

try:
    from sqlite3 import dbapi2 as sqlite #python 2.5 or newer
except:
    try:
        from pysqlite2 import dbapi2 as sqlite
    except:
        exit_module_not_found("pysqlite2")

try:
    from lxml import html, etree
except:
    exit_module_not_found("lxml")

try:
    import pycurl
except:
    exit_module_not_found("pycurl")

#in windows time.clock() have better resolution, in unix the reverse so..
if sys.platform.startswith("win"):
    from time import clock as time_clock
else:
    from time import time as time_clock

class dl_state_class(object):
    """this class store any variables used in the functions that handle the download of the file"""
    def __init__(self):
        self.filename = self.internal_path = ""
        self.dl_prev = 0.0
        self.start_time = self.prev_time = None

#we need to maintain a global last dl_state to use in signal if we catch ctrl+c
last_dl_state = None

def main():
    usage = "%prog [options]"
    #we don't fix the course_list because it is growing continously
    course_list_examples = ("saas", "modelthinking", "algo", "nlp", "crypto", "pgm", "gametheory")
    sub_format_list = ("txt", "srt")
    slides_format_list = ("pptx", "ppt", "pdf")
    cookies_browser_list = ("firefox", "chromium")

    #this works under Linux and chromium, in any other combination specify in the -k switch
    user_home = os.getenv('HOME') or os.getenv('USERPROFILE')
    default_cookies_db_path = "%s/.config/chromium/Default/Cookies" % user_home

    parser = OptionParser(usage)
    p_add_option = parser.add_option #faster local alias

    p_add_option("-x", "--verbose", action="store_true", dest="verbose", default=False,\
                 help="verbose print log messages to console, default: False")

    p_add_option("-c", "--course", dest="course",\
                 help=u"the course url path inside www.coursera.org examples: %s" % u", ".join(course_list_examples))

    p_add_option("-o", "--output-folder", dest="output_folder",\
                 help="the folder where we will store and sync our downloads")

    p_add_option("-b", "--cookies-browser", choices=cookies_browser_list, dest="cookies_browser", default="chromium",\
                 help="the browser from where we are going to read the needed cookies, default: chromium,"\
                 u" options: %s" % u", ".join(cookies_browser_list))

    p_add_option("-k", "--cookies-db-path", dest="cookies_db_path", default=default_cookies_db_path,\
                 help="the path for the selected browser sqlite cookies storage file,"\
                 " default: %s" % default_cookies_db_path)

    p_add_option("-v", "--download-videos", action="store_true", dest="download_videos", default=False,\
                 help="download selected course videos, default: False")

    p_add_option("-s", "--download-subtitles", action="store_true", dest="download_subtitles", default=False,\
                 help="download selected course subtitles, default: False")

    p_add_option("-f", "--subtitles-format", choices=sub_format_list, dest="subtitles_format", default="srt",\
                 help="the format for the subtitles to download: %s, default: srt" % u", ".join(sub_format_list))

    p_add_option("-i", "--download-slides", action="store_true", dest="download_slides", default=False,\
                 help="download selected course slides (links in videos page), default: False")

    p_add_option("-p", "--slides-format", choices=slides_format_list, dest="slides_format", default="pdf",\
                 help="the format for the slides to download: %s, default: pdf" % u", ".join(slides_format_list))

    p_add_option("-m", "--max-bandwith", dest="max_bandwith", default=None,\
                 help="maximum bandwith to use in downloads in bytes/s, default: None")

    p_add_option("-r", "--search-string-section", dest="search_string_section",\
                 help="let's specify a search string to download only the section that have this text in his name")

    p_add_option("-d", "--disable-progressbar", action="store_true", dest="disable_progressbar", default=False,\
                 help="disable the progress bar shown downloading files")

    (options, args) = parser.parse_args()

    #sanity checks, this already prints out the usage help in case of fail.
    #this checks doesn't guarantee correctness but if they pass we can try to execute.
    if not options.course:
        parser.error("You need to specify one of the Coursera courses")
        return

    elif not options.output_folder:
        parser.error("You need to specify the output folder")
        return

    elif not os.path.exists(options.output_folder) or not os.path.isdir(options.output_folder):
        parser.error("Your output folder does not exists or it is not a directory")
        return

    elif not os.path.exists(options.cookies_db_path) or not os.path.isfile(options.cookies_db_path):
        parser.error("Your cookies db path does not exists or it is not a file")
        return

    elif not options.download_subtitles and not options.download_videos and not options.download_slides:
        parser.error("You have not selected nothing for download")
        return

    #we setup the logger
    log_filename = 'coursera_downloader.log'

    my_logger = logging.getLogger('Coursera_Downloader')
    my_logger.setLevel(logging.DEBUG)

    if options.verbose:
        # create console handler and set level to debug
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        ch.setFormatter(formatter)
        my_logger.addHandler(ch)

    handler = logging.handlers.RotatingFileHandler(log_filename, maxBytes=12000, backupCount=0)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    my_logger.addHandler(handler)

    cookies_db_path = options.cookies_db_path
    if sys.platform.startswith("win"): #we assume latin-1 encoding for now.
        try:
            cookies_db_path = unicode(options.cookies_db_path).encode("utf-8")
        except:
            cookies_db_path = options.cookies_db_path.decode("latin-1").encode("utf-8")

    my_logger.debug("Loading cookies from %s" % cookies_db_path)
    ok, num_cookies, cookie_jar = sqlite_to_cookiejar(options.cookies_browser, cookies_db_path)
    if not ok:
        my_logger.error("Can't parse the cookies from the path selected to the browser selected")
        return

    elif num_cookies == 0:
        my_logger.error("Can't find the cookies for Coursera in the cookies db file")
        return

    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookiejar=cookie_jar))
    urllib2.install_opener(opener)

    #post cookie
    url_string = "https://class.coursera.org/%s/lecture/index" % options.course

    #given that we permit user to put any text like course we check it exits.
    try:
        my_logger.debug("Opening URL %s" % url_string)
        complete_html = urllib2.urlopen(url_string).read()
    except:
        my_logger.error("Can't open %s, do the course name exists? did Coursera change the url format?" % url_string)
        return

    output_folder = options.output_folder
    #we create cookies.txt for libcurl
    try:
        my_logger.debug("Dumping cookies.txt to use from libcurl")
        cookies_filename = (u"%s/cookies.txt" % output_folder).encode("utf-8")
        cookie_jar.save(cookies_filename)
    except:
        my_logger.error("error trying to write cookies.txt to use later with libcurl")
        return

    #what to download
    down_sub = options.download_subtitles
    down_vid = options.download_videos
    down_slides = options.download_slides

    #subtitles format
    sub_format = options.subtitles_format #used in loop
    rege = re.compile(r"format\=...")
    subt_replace = "format=%s" % sub_format

    #slides format
    slides_format = options.slides_format

    #scrapping stuff
    try:
        my_logger.debug("Parsing HTML...")
        my_tree = html.fromstring(complete_html)
    except:
        my_logger.error("can't get an html tree from the videos url, maybe the url have changed?")
        return

    try:
        content = my_tree.xpath('//div[@class="item_list"]')[0]
    except:
        my_logger.error("parsing error with the html videos page of the course while getting the content,"\
                        " maybe something have changed?")
        return

    sections_titles = [section.text for section in content.xpath('//h3[@class="list_header"]')]
    sections = content.xpath('./ul[@class="item_section_list"]')

    if not sections_titles or not sections:
        my_logger.error("parsing error with the html videos page of the course while getting the sections,"\
                        " maybe something have changed?")
        return

    parser_get_href = False #only it is a control state for check after the for loop that we have got something.
    max_bandwith = int(options.max_bandwith) if options.max_bandwith else None #faster alias
    search_string_section = options.search_string_section.lower() if options.search_string_section else None

    #any compiled xpath used in loop
    lessons_xpath = etree.XPath('./li[contains(@class, "item_row")]')
    resources_xpath = etree.XPath('./div[@class="item_resource"]/a')
    section_title_xpath = etree.XPath("./a")

    # i know that use a section_num in loop like this it is not perfect, any teachers add sections at the beginning
    # anytimes, SaaS for example added a Saas chat at the beggining two weeks after course init but i still
    # think it is important to know internal order other than chapter or week or internal section enumeration they use,
    # section order becomes important many times because in the same week you should see sections in order to
    # understand them
    section_num = 0
    section_num_re = re.compile(r"^(?P<section_num>\d{2})")

    #we cache this result to search for section folders just in case section_num it is not valid
    listdir_output = os.listdir(output_folder)

    #regex for clean sections and titles from invalid chars, this all areinvalid chars on windows, given that
    #i would like to make compatible the downloader for begin a download and windows and finish in linux for example
    #i replace this chars in all platforms.
    inv_path_re = re.compile(r'[:|?|*|<|>|"|\||/|\\]')
    #we use this dict for replacements.
    inv_path_dict = {':': "_",
                     '?': "",
                     '*': "",
                     '<': " ",
                     '>': " ",
                     '"': "'",
                     '|': " ",
                     '/': "-",
                     '\\': "-",
                     '\n': ""}

    def clean_path(path):
        return inv_path_re.sub(lambda x: inv_path_dict[x.group()], path).strip()

    for section, section_title in izip(sections, sections_titles):
        #fix section title to be possible to create the directory in the different operating systems
        section_title = clean_path(section_title)
        section_num += 1

        if search_string_section is not None and search_string_section not in section_title.lower():
            my_logger.debug("Skipping section %s" % section_title)
            continue
        else:
            my_logger.debug("Checking section %s" % section_title)

        lessons = lessons_xpath(section)

        #for every lesson inside a section we begin an autonumeration to store the correct order
        #i have not found any course modifying this one yet so i am not taking so much care with this one.
        lesson_num = 0
        for lesson in lessons:
            lesson_num += 1
            #fix lesson title to be possible to create the file in the different operating systems
            lesson_title = section_title_xpath(lesson)[0].text.replace("\n", "")
            lesson_title = clean_path(lesson_title)

            section_dir = u"%s/%02d %s" % (output_folder, section_num, section_title)

            #if not exists first we search for it ignoring enumeration and use the folder if found,
            #otherwise we create it
            if not os.path.exists(section_dir):
                folder_found = False
                section_title_lower = section_title.lower()

                for loop_dir in listdir_output:
                    if section_title_lower in loop_dir.lower() and os.path.isdir(u"%s/%s" % (output_folder, loop_dir)):
                        folder_found = True
                        break

                if folder_found:
                    section_dir = u"%s/%s" % (output_folder, loop_dir)
                    #we try to get the sequence number from it, and continue from that if found
                    match_obj = section_num_re.search(loop_dir)
                    if match_obj:
                        section_num = int(match_obj.group("section_num"))

                else: #if not found we create it.
                    try:
                        os.mkdir(section_dir)
                    except OSError:
                        my_logger.error("error creating the directory of the section '%s'" % section_title)
                        return

            resources = resources_xpath(lesson)

            for res in resources:
                if "href" in res.attrib:
                    parser_get_href = True
                else:
                    my_logger.error("parsing error getting the href o a lesson resource, maybe something have changed?")
                    return

                href = res.attrib["href"]

                filename = None
                if down_slides and href[-len(slides_format):] == slides_format:
                    filename = u"%s.%s" % (lesson_title, slides_format)

                elif down_sub and "lecture/subtitles" in href:
                    href = rege.sub(subt_replace, href)
                    filename = u"%s.%s" % (lesson_title, sub_format)

                elif down_vid and "lecture/download.mp4" in href:
                    filename = u"%s.mp4" % lesson_title

                if filename is not None:
                    final_filename = "%02d %s" % (lesson_num, filename)
                    complete_path = u"%s/%s" % (section_dir, final_filename)

                    #first we check if exists with lesson_num, it not, we try without lesson num, if not download it.
                    if os.path.exists(complete_path) and os.path.getsize(complete_path) != 0.0:
                        continue

                    check_path = u"%s/%s" % (section_dir, filename)
                    if os.path.exists(check_path) and os.path.getsize(check_path) != 0.0:
                        continue

                    dl_state = dl_state_class()
                    dl_state.filename = final_filename
                    #we clean the output folder to use in our messages to the user about the active file.
                    dl_state.internal_path = complete_path.replace((output_folder+"/"), "")

                    global last_dl_state #needed for catch ctrl+c signal.
                    last_dl_state = dl_state

                    download_resource(href, complete_path, max_bandwith, cookies_filename, my_logger,\
                                      dl_state, options.disable_progressbar)

    if not parser_get_href:
        my_logger.error("we didn't find links for resources in the lectures html, maybe something have changed?")
        return

    return True

def curl_progress(disable_progressbar, dl_state, dl_total, dl_now, ul_total, ul_now):
    """callback assigned to pycurl download, showing progress (if not disabled)"""
    if disable_progressbar:
        return
    #if the downloaded size did not change we don't update.
    elif dl_now == dl_state.dl_prev:
        return

    cur_time = time_clock()
    #if it is not the last update (for dl completed), we only print one every 0.3 seconds.
    if dl_total != dl_now and (cur_time - dl_state.prev_time) < 0.3:
        return
    #just in case time has not enoguh accuracy
    elif cur_time == dl_state.prev_time:
        return

    avg_speed = dl_now / (cur_time - dl_state.start_time) / 1000.0
    cur_speed = (dl_now - dl_state.dl_prev) / (cur_time - dl_state.prev_time) / 1000.0

    #now we update dl_state
    dl_state.prev_time = cur_time
    dl_state.dl_prev = dl_now

    percent = 0.0
    if dl_total != 0.0:
        percent = float(dl_now) / float(dl_total) * 100.0

    texto = u"\r[%s] %.2f%% downloaded %d/%d avg:%dKb/s cur:%dKb/s" %\
            ("#"*(int(percent)/10), percent, dl_now, dl_total, avg_speed, cur_speed)
    sys.stdout.write(texto)
    sys.stdout.flush()

def download_resource(url, filename, rate_limit, cookies_filename, my_logger, dl_state, disable_progressbar):
    """this function use pycurl to download the file"""
    my_logger.debug("Downloading '%s' from '%s' ...\n" % (filename, url))
    print "Downloading '%s'" % dl_state.internal_path

    #we update this here so we can know what file we are working on if we get stopped by signal.
    global cur_internal_path
    cur_internal_path = dl_state.internal_path

    curl = pycurl.Curl()
    curl.setopt(curl.URL, url)

    if rate_limit is not None:
        curl.setopt(curl.MAX_RECV_SPEED_LARGE, rate_limit)

    file_store = open(filename, "wb")
    curl.setopt(curl.WRITEDATA, file_store)

    #we ever activate progress handling in libcurl to permits the usage of ctrl+c to abort
    #our function curl_progress check that it is not disabled before print it.
    curl.setopt(curl.NOPROGRESS, 0)
    curl.setopt(curl.PROGRESSFUNCTION, functools.partial(curl_progress, disable_progressbar, dl_state))

    curl.setopt(curl.FOLLOWLOCATION, 1) #needed for videos.

    #needed in windows because libcurl don't use the certificates from browsers.
    if sys.platform.startswith("win"):
        curl.setopt(curl.SSL_VERIFYPEER, 0)

    #cookies
    curl.setopt(curl.COOKIEJAR, cookies_filename)
    curl.setopt(curl.COOKIEFILE, cookies_filename)

    #we set start time and prev_time
    dl_state.start_time = dl_state.prev_time = time_clock()

    try:
        curl.perform()
    except:
        import traceback
        my_logger.error(u"Error downloading file: %s" % traceback.format_exc())

    #cleaning
    curl.close()
    file_store.close()
    print "\n" #change line for progress
    return

def sqlite_to_cookiejar(browser, filename):
    """create a cookies.txt from Firefox or Chromium browsers cookies sqlite files, this cookies.txt
    files can be use with urllib2 or pycurl"""
    try:
        con = sqlite.connect(filename)
    except sqlite.DatabaseError, sqlite.OperationalError:
        return False, 0, None

    con.text_factory = str
    cur = con.cursor()

    if browser == "firefox":
        sql_txt = u"""
            SELECT host,
            path,
            isSecure,
            expiry,
            name,
            value
            FROM moz_cookies
            WHERE host LIKE ?
            """
    elif browser == "chromium":
        sql_txt = u"""
            SELECT host_key,
            path,
            secure,
            expires_utc,
            name,
            value
            FROM cookies
            WHERE host_key LIKE ?
            """

    else:
        return False, 0, None

    cur.execute(sql_txt, ('%coursera%',))

    ftstr = ["FALSE", "TRUE"]

    s = StringIO()
    sWrite = s.write #fast local alias

    sWrite("""\
# Netscape HTTP Cookie File
# http://www.netscape.com/newsref/std/cookie_spec.html
# This is a generated file! Do not edit.
""")

    num_cookies = 0
    for host, path, secure, expiry, name, value in cur:
        num_cookies += 1
        sWrite("%s\t%s\t%s\t%s\t%s\t%s\t%s\n" % (host, ftstr[host.startswith('.')], path,\
                                                 ftstr[secure], expiry, name, value))

    cur.close()
    s.seek(0)

    cookie_jar = cookielib.MozillaCookieJar()
    cookie_jar._really_load(s, '', True, True)

    return True, num_cookies, cookie_jar

def signal_handler(signal, frame):
    """used to catch ctrl+c stopping the process"""
    print "\n\nYou pressed Ctrl+C, exiting!"
    # we tell the user that he should delete manually the in-progress file given that in any platforms,
    # windows (at least), the file would be blocked by the download process
    if last_dl_state is not None:
        print "You should delete manually the file '%s'" % last_dl_state.internal_path

    sys.exit(1)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    main()