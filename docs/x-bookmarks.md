# Exporting your X bookmarks

X's own data download leaves bookmarks out, and the API that returns them is paid. This page
explains how to save your bookmarks yourself with a short script, `tools/x-bookmarks-capture.js`,
and how to import the files into the backlog. Plan on about ten minutes per account, most of it
scrolling.

## What the script does, and what it doesn't

When you scroll x.com/i/bookmarks, X's page asks X for your bookmarks a page at a time. The
script listens for X's answers to those requests and keeps a copy in the tab's memory. When you
press **Save file**, it downloads everything it kept as one JSON file.

The script sends no requests of its own, loads no other code, and never scrolls or clicks for you.
It only adds a small panel to the page. It is under 200 lines long, so read it in full before
you run it. Closing or reloading the tab throws away anything you have not saved.

**X's terms.** X's Terms of Service prohibit crawling or scraping the service without X's written
consent. This script does not crawl: it keeps copies of the answers your own browser already
receives while you scroll by hand. Whether that still counts as scraping under X's terms is your
call to make for your own account. X may read its terms differently from how we do.

## Save the bookmarks of one account

1. In Chrome, sign in to x.com with the account and open **x.com/home**. Reload the page once,
   so that this tab has not loaded your bookmarks yet.
2. Open the console with **Cmd+Option+J**. The first time, Chrome asks you to type
   `allow pasting` before it accepts pasted code.
3. Paste the whole of `tools/x-bookmarks-capture.js` and press Return. A panel appears at the top
   right of the page and says it is waiting.
4. Click **Bookmarks** in the left sidebar. Don't type the address instead, because loading a new
   address reloads the page and stops the script. The panel should now say "The first page was
   captured." If it says the first page was missed, X reused a page it had already loaded. Reload
   x.com/home and start again from step 3.
5. Scroll down through your bookmarks by hand, at your own pace. The post count grows each time X
   loads another page.
6. At the bottom, X should answer the request for the next page with an empty page. The panel
   then says "X returned an empty page, so this is the end of what X will show," and the count
   stops growing. (Your first capture will confirm that X behaves this way.)
7. Press **Save file**. The script suggests the account's handle; check it and press OK. Chrome
   saves `x-bookmarks-<handle>-<date>.json` in Downloads. Move it into `~/Downloads/x-bookmarks/`.
8. Note the panel's post count for this account, then switch to the other account and repeat
   from step 1.

You can press **Save file** more than once. Each file holds everything captured so far, and the
import merges repeated posts, but it is simplest to keep only the latest file for each account.

**If the panel says pages failed,** X is limiting how fast you can load. Stop scrolling and leave
the tab open, because reloading it throws away the capture. Wait about 15 minutes, then scroll
again, or press X's own Retry button if it shows one. When a failed page loads, the panel stops
counting it as failed. If it keeps failing, save what you have and try another day.

**If X stops loading before the panel says it reached the end,** or the count stops short of what
you expect, save the file and note both numbers. The web page may show at most about 800
bookmarks, as X's API does, but nobody has confirmed that.

**Instead of pasting it each time,** you can install the same file as a userscript in Tampermonkey
or Violentmonkey. Create a new script and paste the file in. It should then start before the page
loads, so it sees the first page too, and the panel still tells you if it missed it. Open
x.com/i/bookmarks directly, and turn the script off when you are done.

## Import the files

Both accounts import together as one backlog. Each post records which accounts bookmarked it,
and a post saved by both accounts appears once.

```bash
python3 -m techdigest backlog import ~/Downloads/x-bookmarks
```

It prints counts. `captures` has one entry per file. In it, `posts` should match the panel's
count, `unavailable` counts bookmarked posts that were deleted or made private, `failed_pages`
should be 0, and `first_page` and `reached_end` should both be true. `posts_by_account` and
`posts_in_several_accounts` show how the accounts overlap. A warning (exit code 3) names what to
fix, such as a missed first page, a capture that stopped before the end, or a file saved without
a handle.

The files hold the full text of everything you bookmarked. Keep them out of the repository: the
import writes to `backlog/raw/`, which git ignores. The import also still reads a JSON export from
the twitter-web-exporter userscript and the X archive's `bookmark.js`.
