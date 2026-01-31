import optparse
import os
import sys


def options():
    prog = os.path.basename(sys.argv[0])

    p = optparse.OptionParser(
        usage=f"{prog} [options] [url]",
        description="nobi-dl – scrape-based movie & series downloader",
    )

    p.add_option(
        "--search",
        dest="search",
        metavar="QUERY",
        help="Search for a movie or series instead of providing a direct URL",
    )

    p.add_option(
        "-v",
        "--verbose",
        action="count",
        dest="verbose",
        default=0,
        help="Increase verbosity (-v, -vv)",
    )

    p.add_option(
        "-q",
        "--quiet",
        action="store_true",
        dest="quiet",
        default=False,
        help="Suppress non-essential output",
    )

    p.add_option(
        "--parse-network",
        action="store_true",
        dest="parse_network",
        default=False,
        help="Parse network requests to extract hidden media URLs",
    )

    p.add_option(
        "-F",
        "--list-formats",
        action="store_true",
        dest="list_formats",
        default=False,
        help="List all available formats without downloading",
    )

    p.add_option(
        "--impersonate",
        dest="impersonate",
        metavar="BROWSER",
        default=None,
        help="Impersonate a browser (e.g. chrome, firefox, safari)",
    )

    p.add_option(
        "--print-traffic",
        action="store_true",
        dest="print_traffic",
        default=False,
        help="Print sent and received HTTP traffic",
    )

    p.add_option(
        "-j",
        "--dump-json",
        action="store_true",
        dest="dump_json",
        default=False,
        help="Dump extracted info as JSON to stdout",
    )

    p.add_option(
        "--list-impersonate-targets",
        action="store_true",
        dest="list_impersonate",
        default=False,
        help="List all supported impersonation targets",
    )

    p.add_option(
        "-c",
        "--continue",
        action="store_true",
        dest="continue_dl",
        default=False,
        help="Resume partially downloaded files if possible",
    )

    p.add_option(
        "--list-extractors",
        action="store_true",
        dest="list_extractors",
        default=False,
        help="List all available extractors",
    )

    p.add_option(
        "--extractor",
        dest="force_extractor",
        metavar="NAME",
        default=None,
        help="Force a specific extractor to be used",
    )

    p.add_option(
        "--version",
        action="store_true",
        dest="show_version",
        help="Show program version and exit",
    )

    opts, args = p.parse_args()

    if opts.show_version:
        from nobi_dl.version import __version__
        p.exit(0, f"nobi-dl {__version__}\n")
    
    opts.movie_url = args[0] if (args and not opts.search) else None

    if (
        not opts.movie_url
        and not opts.search
        and not opts.list_impersonate
        and not opts.list_extractors
    ):
        p.error("Provide a URL or use --search QUERY")

    return opts, args, p.error
