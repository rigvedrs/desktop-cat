DESKTOP CAT
===========

A small cat that sits on top of everything on your screen. It taps its paws
while you type, closes its eyes and sends up hearts when you pet it, and
curls up for a nap when you go quiet.


-----------------------------------------------------------------------
FOR YOU (once)
-----------------------------------------------------------------------

ON A MAC, or with no Windows machine at all:
    read BUILD-FROM-MAC.txt -- GitHub builds the exe for you, free.
    You can also preview the cat live on the Mac in about two minutes.

ON A WINDOWS LAPTOP:
    double-click build.bat and wait.

When it finishes it opens a folder containing:

    dist\DesktopCat.exe

That one file is the whole app. Send it to anyone. They double-click it and
the cat appears. No Python, no install, no setup on their side.

If build.bat says Python is missing, get it from python.org and tick
"Add python.exe to PATH" on the installer's first screen, then run it again.

Expect the exe to be roughly 50-80 MB, because the drawing engine is baked
in. Too big for email; use Drive, WeTransfer or a USB stick.


-----------------------------------------------------------------------
FOR THE PEOPLE YOU SEND IT TO
-----------------------------------------------------------------------

Double-click DesktopCat.exe. The cat appears near the bottom-right.

  Drag it              move it anywhere on screen
  Hover and wiggle     pet it (hearts)
  Click it             a quick pet
  Right-click it       menu: cat, eyes, size, and so on
  Tray icon            same menu, and click it to fetch the cat back

The menu has four cats (Nyx, Nora, Nemo, Noir), two eye styles
(round pupils or slim pupils), three sizes, "Start with Windows", and
"Click through" for when the cat is in the way but you want it visible.

Settings and position are remembered in:
    %APPDATA%\DesktopCat\settings.json

To close it: right-click the cat, then Quit.
Opening it twice does nothing -- the second copy exits, so nobody ends up
with two cats.


-----------------------------------------------------------------------
WHAT A RECIPIENT ACTUALLY NEEDS
-----------------------------------------------------------------------

Nothing. No Python, no Qt, no runtime, no admin rights, no Store account.
It writes only to its own settings file and unpacks itself into the temp
folder. Windows 10 or 11, which any new laptop has.

Three things can still get in the way. Ranked by how likely they are on a
cheap, new, non-technical laptop:

1. S MODE  -- the one that actually blocks it

   Budget laptops often ship in Windows 11 S mode, which refuses to run
   any program that didn't come from the Microsoft Store. There is no
   "run anyway" here; the app simply won't start, or Windows offers a
   Store page instead.

   The fix is free and takes a minute, in
   Settings > System > Activation > "Switch out of S mode".
   It is a one-way change though, so it's their call, not yours. Worth
   asking before you send the file.

2. THE BLUE SMARTSCREEN BOX -- likely, but only a speed bump

   "Windows protected your PC" > More info > Run anyway.
   Every unsigned program gets this. The only real fix is a code-signing
   certificate, roughly $100-400 a year from a provider like DigiCert or
   Sectigo. The warning also fades by itself once enough people have run
   the same file.

3. THE PREINSTALLED ANTIVIRUS TRIAL -- occasionally

   New laptops often come with a McAfee or Norton trial, and those are
   more trigger-happy than Windows Defender about PyInstaller programs.
   If one quarantines the file, it needs allow-listing.

Two smaller notes. On an ARM laptop (a Snapdragon Copilot+ PC) the exe
runs through Windows' x64 emulation -- it works, it just starts a little
slower. And the first launch on any machine takes several seconds while
the exe unpacks, which is why there's a splash screen; without it people
assume nothing happened and double-click again.

SEND-THIS-WITH-THE-FILE.txt is a plain-language version of all of the
above, written for the person receiving it. Forward it with the exe.


-----------------------------------------------------------------------
HOW THE TYPING DETECTION WORKS
-----------------------------------------------------------------------

Sixteen times a second the app asks Windows one question: "has any typing
key been pressed since I last asked?" It gets back yes or no. It never
learns which key, never stores anything, and never sends anything anywhere.
The only thing it does with the answer is lift a paw.

This is worth being able to explain, because "app that reacts to your
typing" sounds worse than it is, and someone will ask.


-----------------------------------------------------------------------
CHANGING THE ART
-----------------------------------------------------------------------

Everything the cat is made of lives at the top of cat.py as plain SVG on a
120 x 132 canvas. The CATS list holds the four colour schemes; adding a
fifth cat is one more entry in that list. The eyes are drawn by the
functions in EYE_PARTS (iris, pupil and catchlights for each style).

Windows only. It leans on Windows for the always-on-top behaviour, the
typing check and the tray icon.
