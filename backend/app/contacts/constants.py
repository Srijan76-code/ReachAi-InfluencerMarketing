"""Settings for finding creators' contact details (spec §7.1). Free sources only (decided Nov 14): the creator's
own bio, their link-in-bio page, and their own website. No paid finders or verifiers."""

# Link-in-bio pages: everything on them is the creator's own, so emails and social links there count.
LINK_PAGE_HOSTS = (
    "linktr.ee", "beacons.ai", "stan.store", "bio.link", "lnk.bio", "linkin.bio", "campsite.bio", "hoo.be",
    "komi.io", "solo.to", "tap.bio", "msha.ke", "allmylinks.com", "bento.me", "carrd.co", "linkpop.com",
    "snipfeed.co", "koji.to", "withkoji.com", "direct.me", "linkbio.co", "milkshake.app", "flowcode.com",
    "taplink.cc", "linktree.com", "biolinky.co", "contactinbio.com",
)
# Not a personal website: no contact page worth reading (stores, platforms, podcasts, shorteners we don't follow).
NOT_A_WEBSITE_HOSTS = (
    "youtube.com", "youtu.be", "instagram.com", "x.com", "twitter.com", "tiktok.com", "facebook.com", "fb.com",
    "linkedin.com", "threads.net", "t.me", "telegram.me", "wa.me", "whatsapp.com", "discord.gg", "discord.com",
    "reddit.com", "pinterest.com", "twitch.tv", "spotify.com", "apple.com", "amazon.com", "amzn.to", "amzn.eu",
    "flipkart.com", "patreon.com", "buymeacoffee.com", "ko-fi.com", "paypal.me", "paypal.com", "gumroad.com",
    "github.com", "medium.com", "substack.com", "google.com", "goo.gl", "forms.gle", "docs.google.com",
    "drive.google.com", "play.google.com", "apps.apple.com", "calendly.com", "zoom.us", "shopify.com",
    "myshopify.com", "etsy.com", "udemy.com", "skillshare.com", "coursera.org", "notion.so", "notion.site",
    "bit.ly", "tinyurl.com", "geni.us", "rebrand.ly", "linkedin.cn",
)
# A link or path on a website that probably holds a business contact.
CONTACT_HINTS = ("contact", "about", "collab", "business", "sponsor", "work-with", "workwithme", "partner",
                 "advertis", "press", "media-kit", "mediakit", "brands", "hire")
FALLBACK_CONTACT_PATH = "/contact"

FETCH_TIMEOUT_S = 6.0
MAX_PAGE_BYTES = 600_000
MAX_REDIRECTS = 3
MAX_PAGES_PER_CREATOR = 6  # link pages + website pages, all the person's accounts together
MAX_WEBSITES_PER_CREATOR = 2
CONTACT_PAGES_PER_WEBSITE = 2
FIND_CONCURRENCY = 8  # creators looked up at once
USER_AGENT = "Mozilla/5.0 (compatible; ReachAI/1.0; +https://reachai.app)"

# Where an address came from, best first. The creator's own bio beats their link page beats their website.
SOURCE_RANK = {"bio": 0, "link_page": 1, "website": 2}
# Addresses on a business role inbox read as the right one for a sponsorship.
BUSINESS_LOCAL_PARTS = ("business", "collab", "collabs", "partnership", "partnerships", "sponsor", "sponsorship",
                        "sponsorships", "brand", "brands", "booking", "bookings", "work", "inquiries",
                        "enquiries", "inquiry", "enquiry", "contact", "hello", "hi", "team", "media", "press",
                        "management", "mgmt")
NEVER_LOCAL_PARTS = ("noreply", "no-reply", "donotreply", "do-not-reply", "mailer-daemon", "postmaster",
                     "abuse", "privacy", "unsubscribe", "bounce", "example", "yourname", "name", "email", "user",
                     "username", "test")
JUNK_DOMAINS = ("example.com", "example.org", "domain.com", "email.com", "sentry.io", "sentry-next.wixpress.com",
                "wixpress.com", "wix.com", "squarespace.com", "godaddy.com", "yourdomain.com", "mysite.com",
                "website.com", "company.com", "test.com")
JUNK_TLDS = ("png", "jpg", "jpeg", "gif", "webp", "svg", "css", "js", "ico", "mp4", "pdf")
# Big inboxes that always accept mail: no DNS check needed.
KNOWN_MAIL_DOMAINS = ("gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com", "yahoo.com",
                      "icloud.com", "me.com", "proton.me", "protonmail.com", "aol.com", "zoho.com", "yandex.com",
                      "gmx.com", "mail.com", "hey.com", "fastmail.com", "rediffmail.com", "yahoo.co.in",
                      "outlook.in", "hotmail.co.uk", "yahoo.co.uk")
# DNS over HTTPS, free and keyless, to check a domain can receive email (MX, else A record).
DOH_URLS = ("https://cloudflare-dns.com/dns-query", "https://dns.google/resolve")

# An address listed by this many different people is an agency's or a sponsor's: used only if nothing else is.
SHARED_ADDRESS_MIN_PEOPLE = 3

# Jev checks the pick when there's a choice to make, or when the address came from a website page.
JEV_PICK_MIN = 0.8
JEV_NAME_MIN = 0.7
MAX_EMAIL_CHOICES = 6
MAX_NAME_CHOICES = 6

# Look again after this many days (contact details change; results are cached on the creator).
RESEARCH_AFTER_DAYS = 30
# Warn before contacting someone the same founder already contacted this recently.
RECENTLY_CONTACTED_DAYS = 90
