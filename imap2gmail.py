#!/usr/bin/python -OO
##################################################################
# CONFIG: Change these constants if you wish.
##################################################################

# This is overridden by the command-line argument if present.
DEFAULT_SMTP = 'gsmtp57.google.com'

# Time to wait between sending of each message to the SMTP server.
SMTP_SLEEP_INTERVAL = 2

##################################################################
# End CONFIG
##################################################################



# Command-line documentation... you'll have to figure out how to use the code direct from python ;-)
__doc__ = """
-i --imap_server    Sets the IMAP server that the to-be-exported-into-GMail messages currently reside on. (REQUIRED)
-u --user           Sets the username used to login to the IMAP server. (REQUIRED)
-t --to             Sets the gmail address that the messages are to be exported to. (REQUIRED)
-s --subroot        Sets the IMAP folder path that must be matched for all exports. (OPTIONAL)
                    e.g. 'INBOX.a_folder' would export all messages in INBOX.a_folder and its subfolders.
-r --smtp           Sets the SMTP server to use for sending the messages to GMail.  Defaults to '%s'. (OPTIONAL)
-p --passw          Sets the password used to login to the IMAP server.
                    If unspecified, user prompted to input it. (OPTIONAL)
-m --munge_subject  If this argument is present, the original IMAP folder path of each message is shoved into the
                    subject header. (OPTIONAL)
                    e.g. Subject: original subject [INBOX.a_folder]
                    "Yuck!", I hear you say.  Indeed.  But GMail won't filter on arbitrary headers (2004/8/10),
                    so this hack may be necessary for some.  If you're confident that GMail will soon allow you to
                    search/filter on arbitrary headers, you can forget about this.  The folder path is stuffed into
                    the 'X-Mail-Folder' header, and the flags are put into 'X-Flags', no matter whether you choose to
                    munge your subject or not.
-h --help           Displays this text.
""" % DEFAULT_SMTP


import imaplib, re, time, smtplib, sys, getpass, getopt
from email import message_from_string as mfs
from types import TupleType


folder_flags_re = re.compile('\A\((.*?)\)')
flags_re = re.compile('FLAGS \((.*?)\)')


class FolderListParser:
    """Parse, for example, this:
        '(\\NoInferiors \\Marked) "/" ~/mail/bris-zope'
    """

    def __init__(self, s):
        self._s = s

    def getFolderFlags(self):
        return folder_flags_re.findall(self._s)[0].split(' ')

    def getSeparator(self):
        ind = self._s.find('"')
        return self._s[ind+1:ind+2]

    def getPath(self):
        try:
            ind = self._s.find('"')
        except AttributeError:
            raise Exception(self._s)
        if self._s[ind+4] == '"':
            return self._s[ind+5:-1]
        return self._s[ind+4:]


class Logger:
    """A logger that doesn't complain about not being able to 'write'.
    """

    def __init__(self, log=None):
        self.log = log

    def write(self, text):
        if hasattr(self.log, 'write'):
            self.log.write(text)
        self.flush()

    def flush(self):
        if hasattr(self.log, 'flush'):
            self.log.flush()


class ProgressBar:
    """A simple progress bar, that's really meant for writing to sys.stdout,
    but will quite happily 'write' to anything that will let it.
    """

    def __init__(self, max_value, title='Progress Bar', logger=Logger()):
        self.max_value = max_value
        self.count = 0
        self.print_count = 0
        self.title = title
        self.logger = logger
        self.logger.write("""%s:
0-----------------------25-----------------------50-----------------------75---------------------100
""" % self.title )

    def _calculateCorrectPrintCount(self, count):
        if self.max_value == 0:
            return 100
        return divmod(count*100, self.max_value)[0]

    def logProgress(self, increment):
        new_count = self.count + increment
        correct_print_count = self._calculateCorrectPrintCount(new_count)
        if correct_print_count > self.print_count:
            diff = correct_print_count - self.print_count
            self.logger.write('#' * diff)
        self.count = new_count
        self.print_count = correct_print_count

    def finish(self, text=None):
        if self.print_count != self.max_value or self.max_value == 0:
            correct_print_count = self._calculateCorrectPrintCount(self.max_value)
            diff = correct_print_count - self.print_count
            self.logger.write('#' * diff)
        if text is None:
            text = 'Complete!'
        self.logger.write('\n%s\n\n' % text) 


class IMAPFolder:

    def __init__(self, path, logger=Logger()):
        self.path = path
        self.logger = logger

    def select(self, conn):
        typ, data = conn.select(self.path)
        if typ != 'OK':
            raise Exception('Could not select "%s"' % self.path)
        try:
            msg_count = int(data[0])
        except IndexError:
            msg_count = 0
        return msg_count

    def getMessages(self, conn):
        msg_count = self.select(conn)
        self.logger.write("Fetching %s messages from '%s'\n" % (msg_count, self.path))
        r = conn.fetch('1:*', '(RFC822 FLAGS)')
        messages = []
        if r[0] != 'OK':
            raise Exception('Bad response from server: %s' % r)
        for each in r[1]:
            if isinstance(each, TupleType):
                msg = mfs(each[1])
                # Add flags to X-Flags header
                flags = flags_re.search(each[0])
                if flags:
                    msg['X-Flags'] = ' '.join(flags.groups())
                # Add folder path to X-Mail-Folder
                msg['X-Mail-Folder'] = self.path
                messages.append(msg)
        return (messages, msg_count)


class IMAPAccount:

    def __init__(self, server, user, passw, logger=Logger()):
        self.server = server
        self.user = user
        self.passw = passw
        self.logger = logger
        self._conn = None

    def getConn(self):
        if self._conn is None or self._conn.state != 'AUTH':
            conn = imaplib.IMAP4(self.server)
            conn.login(self.user, self.passw)
            self._conn = conn
            self.logger.write("Connected to '%s' as '%s'\n" % (self.server, self.user))
        return self._conn

    def listFolders(self, subroot=None):
        conn = self.getConn()
        r = conn.list()
        folders = []
        folder_set = []
        if subroot is not None:
            for each in r[1]:
                if each.find(subroot) != -1:
                    folder_set.append(each)
        else:
            folder_set = r[1]
        for each in folder_set:
            p = FolderListParser(each)
            imapfolder = IMAPFolder(p.getPath(), logger=self.logger)
            folders.append(imapfolder)
        folder_paths = [each.path for each in folders]
        self.logger.write("Found IMAP folders: '%s'\n" % "', '".join(folder_paths))
        return folders


class GMailImporter:

    def __init__(  self
                 , imapserver
                 , user
                 , passw
                 , gmailaddr
                 , smtpsrv=DEFAULT_SMTP
                 , subroot=None
                 , mungesubject=None
                 , logger=Logger()
                ):
        self.imapacct = IMAPAccount(imapserver, user, passw, logger)
        self.gmailaddr = gmailaddr
        self.smtpsrv = smtpsrv
        self.subroot = subroot
        self.mungesubject = mungesubject
        self.logger = logger

    def doImport(self):
        server = smtplib.SMTP(self.smtpsrv)
        #server.set_debuglevel(5)
        conn = self.imapacct.getConn()
        folders = self.imapacct.listFolders(self.subroot)
        for folder in folders:
            count = 0
            msgs, msg_count = folder.getMessages(conn)
            progress_title = 'GMail upload progress for %s (%s messages in total)' % (folder.path, msg_count)
            progress_log = ProgressBar(msg_count, progress_title, self.logger)
            for msg in msgs:
                if self.mungesubject:
                    munged_subject = '%s [%s]' % (msg['Subject'], folder.path)
                    msg.replace_header('Subject', munged_subject)
                server.sendmail(msg['From'], self.gmailaddr, msg.as_string())
                progress_log.logProgress(1)
                count += 1
                time.sleep(SMTP_SLEEP_INTERVAL)
            progress_log.finish()
        server.quit()



def usage():
    print __doc__


def main(argv):
    try:
        opts, args = getopt.getopt(  argv
                                   , "hi:u:t:r:s:p:m"
                                   , [  "help"
                                      , "imap_server="
                                      , "user="
                                      , "to="
                                      , "smtp="
                                      , "subroot="
                                      , "munge_subject"
                                      , "passw="
                                      ]
                                   )
    except getopt.GetoptError:
        usage()
        sys.exit(2)
    imap_server = user = gmailaddr = subroot = passw = mungesubject = None
    smtpsrv = DEFAULT_SMTP
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage()
            sys.exit()
        elif opt in ("-i", "--imap_server"):
            imap_server = arg
        elif opt in ("-u", "--user"):
            user = arg
        elif opt in ("-t", "--to"):
            gmailaddr = arg
        elif opt in ("-s", "--subroot"):
            subroot = arg
        elif opt in ("-r", "--smtp"):
            smtpsrv = arg
        elif opt in ("-m", "--munge_subject"):
            mungesubject = 1
        elif opt in ("-p", "--passw"):
            passw = arg
    if imap_server is None or user is None or gmailaddr is None:
        usage()
        sys.exit(2)
    if passw is None:
        passw = getpass.getpass('IMAP server password: ')
    logger = Logger(sys.stdout)
    g = GMailImporter(imap_server, user, passw, gmailaddr, smtpsrv, subroot, mungesubject, logger)
    g.doImport()

if __name__ == '__main__':
    main(sys.argv[1:])
