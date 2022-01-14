"""export mapbox satellite imagery as massive stitched JPG"""

import math
import asyncio
import aiohttp
from PIL import Image
import io
import tkinter
import logging
import sys
import os

logger = logging.getLogger()

ACCESS_TOKEN = 'pk.eyJ1IjoiZG96emFiYiIsImEiOiJja3liaDJieW4wZjhjMm9wajZmM21yeGRkIn0._Gqt3sATAXx1WNvLwv2okQ'

def ask_multiple_choice_question(prompt, options):
    root = tkinter.Tk()
    if prompt:
        tkinter.Label(root, text=prompt).pack()
    v = tkinter.IntVar()
    v.set(0)
    for i, option in enumerate(options):
        tkinter.Radiobutton(root, text=option, variable=v, value=i).pack(anchor="w")
    tkinter.Button(root, text="Submit", command=root.quit).pack(side="top")
    root.mainloop()
    return options[v.get()]


class Map_downloader:
    """Downloads a set of tiles and stitches."""
    def __init__(self,lat_d_1,lon_d_1, lat_d_2,lon_d_2, ZOOM_LEVEL = 10, MAP_TYPE = "GOOGLE"):
        # Initialise self variables.
        root = tkinter.Tk()
        self.root = root
        self.lat_d_1 = tkinter.DoubleVar()
        self.lat_d_1.set(lat_d_1)
        self.lat_d_2 = tkinter.DoubleVar()
        self.lat_d_2.set(lat_d_2)
        self.lon_d_1 = tkinter.DoubleVar()
        self.lon_d_1.set(lon_d_1)
        self.lon_d_2 = tkinter.DoubleVar()
        self.lon_d_2.set(lon_d_2)
        self.MAP_TYPE = tkinter.StringVar()
        self.MAP_TYPE.set(MAP_TYPE)
        self.ZOOM_LEVEL = tkinter.IntVar()
        self.ZOOM_LEVEL.set(ZOOM_LEVEL)
        self.logger = logging.getLogger("Map Downloader")
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(filename)s:%(lineno)s %(message)s'))
        self.logger.addHandler(ch)
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False
        self.logger.debug('Map Downloader Initialised.')

        # Initialise TKinter window hidden.
        # Generate  TKInter window with the following:
        root.title("Map API Downloader v0.1")
        root['padx'] = 20
        root['pady'] = 20
        # lat1
        tkinter.Label(root, justify="left", text="Top Left Latitude").grid(sticky=tkinter.W, row=0, column=0)
        tkinter.Entry(root, textvariable=self.lat_d_1).grid(row=0, column=1)
        # lon1
        tkinter.Label(root, justify="left", text="Top Left Longitude").grid(sticky=tkinter.W,row=1, column=0)
        tkinter.Entry(root, textvariable=self.lon_d_1).grid(row=1, column=1)
        # lat2
        tkinter.Label(root, justify="left", text="Bottom Right Latitude").grid(sticky=tkinter.W,row=2, column=0)
        tkinter.Entry(root, textvariable=self.lat_d_2).grid(row=2, column=1)
        # lon2
        tkinter.Label(root, justify="left", text="Bottom Right Longitude").grid(sticky=tkinter.W,row=3, column=0)
        tkinter.Entry(root, textvariable=self.lon_d_2).grid(row=3, column=1)

        #zoom level
        tkinter.Label(root, justify="left", text="Zoom Level").grid(sticky=tkinter.W,row=4, column=0)
        tkinter.Scale(root, variable=self.ZOOM_LEVEL, orient="horizontal", to=19, from_=10, command=self.calculate_total_tiles).grid(row=4, column=1)
        
        self.total_tiles = tkinter.IntVar()
        tkinter.Label(root, justify="left", text="Total Tiles").grid(sticky=tkinter.W,row=5, column=0)
        tkinter.Label(root, textvariable=self.total_tiles).grid(row=5, column=1)

        # MAP_TYPE
        tkinter.Label(root, justify="left", text="Map Type:").grid(sticky=tkinter.W, row=6)
        tkinter.Radiobutton(root, text="Mapbox", value="MAPBOX", variable=self.MAP_TYPE, command=self.calculate_base_url).grid(sticky=tkinter.W, row=7)
        tkinter.Radiobutton(root, text="Google", value="GOOGLE", variable=self.MAP_TYPE, command=self.calculate_base_url).grid(sticky=tkinter.W, row=8)
        # BASE_URL display debug,
        self.BASE_URL = tkinter.StringVar()
        tkinter.Label(text="BASE_URL").grid(row=7, column=1)
        tkinter.Label(textvariable=self.BASE_URL).grid(row=8, column=1)
        self.calculate_base_url()
        # DOWNLOAD button.
        self.downloadbutton = tkinter.Button(root, text="Download", command=self.download_tiles)
        self.downloadbutton.grid(row=9, column=0)
        # Quit button
        self.status = tkinter.StringVar()
        self.status.set('Ready')

        # init lol
        self.calculate_base_url()
        tkinter.Button(root, text="Quit", command=self.exit).grid(row=10, column=0)
        tkinter.Label(root, textvariable=self.status).grid(row=10, column=1)
        tkinter.Pack()
        root.mainloop()

    def exit(self):
        self.status.set('Exiting..')
        self.root.update()
        sys.exit(0)

    async def fetch(self, session, url, x, y):
        async with session.get(url) as response:
            self.received_tiles += 1
            r = await response.read(),x,y
            if (self.received_tiles % math.ceil(self.total_tiles.get()/100) == 0): # 4% progress indicator
                self.logger.info(f"Received tile {self.received_tiles}/{self.total_tiles.get()}")
                self.status.set(f"Received tile {self.received_tiles}/{self.total_tiles.get()}")
                self.root.update()
            return r

    async def fetch_all(self, urls, loop):
        async with aiohttp.ClientSession(loop=loop) as session:
            results = await asyncio.gather(*[self.fetch(session, url['url'], url['x'], url['y']) for url in urls])
            return results

    def calculate_total_tiles(self, value):
        n = 2 ** self.ZOOM_LEVEL.get()
        self.x1 = math.floor(n * ((self.lon_d_1.get() + 180) / 360))
        self.y1 = math.floor(n * (1- (math.log(math.tan(math.radians(self.lat_d_1.get())) + 1 / math.cos(math.radians(self.lat_d_1.get()))) / math.pi)) / 2)
        self.x2 = math.ceil(n * ((self.lon_d_2.get() + 180) / 360))
        self.y2 = math.ceil(n * (1- (math.log(math.tan(math.radians(self.lat_d_2.get())) + 1 / math.cos(math.radians(self.lat_d_2.get()))) / math.pi)) / 2)
        self.diff_x = self.x2 - self.x1
        self.diff_y = self.y2 - self.y1
        self.total_tiles.set(self.diff_x * self.diff_y)
        self.root.update()

        # self.root.withdraw()
    def calculate_base_url(self):
        self.logger.info(f"Map type is {self.MAP_TYPE.get()}")
        if self.MAP_TYPE.get() == 'GOOGLE':
            self.BASE_URL.set("https://khms0.google.com/kh")
        elif self.MAP_TYPE .get() == 'MAPBOX':
            self.BASE_URL.set("https://api.mapbox.com/v4/mapbox.satellite")
        self.logger.info(f"Base url is {self.BASE_URL.get()}")

    # def ask_configuration(self):
    #     # self.ZOOM_LEVEL = -1
    #     # while (1 > self.ZOOM_LEVEL) or (self.ZOOM_LEVEL > 18): # ask that you choose again.
    #     #     self.ZOOM_LEVEL = simpledialog.askinteger(title="Choose zoom level", prompt="What zoom level would you like to download the map at?")

    #     self.MAP_TYPE = ask_multiple_choice_question("Please choose either MAPBOX or GOOGLE as your source of tiles.", ["MAPBOX","GOOGLE"])
    #     self.logger.debug(f"chosen map type was {self.MAP_TYPE}")
    #     self.calculate_base_url()

    def download_tiles(self):
        try:
            self.status.set('Starting')
            self.downloadbutton['state'] = 'disable'
            n = 2 ** self.ZOOM_LEVEL.get()
            # do something.
            self.logger.info("Downloading Tiles..")
            self.logger.debug(f"zoom level is {self.ZOOM_LEVEL.get()}, n = {n}")
            self.x1 = math.floor(n * ((self.lon_d_1.get() + 180) / 360))
            self.y1 = math.floor(n * (1- (math.log(math.tan(math.radians(self.lat_d_1.get())) + 1 / math.cos(math.radians(self.lat_d_1.get()))) / math.pi)) / 2)
            self.x2 = math.ceil(n * ((self.lon_d_2.get() + 180) / 360))
            self.y2 = math.ceil(n * (1- (math.log(math.tan(math.radians(self.lat_d_2.get())) + 1 / math.cos(math.radians(self.lat_d_2.get()))) / math.pi)) / 2)
            self.diff_x = self.x2 - self.x1
            self.diff_y = self.y2 - self.y1
            self.total_tiles.set(self.diff_x * self.diff_x)
            self.logger.debug(f"downloading {self.total_tiles.get()} tiles")
            self.img_h = self.diff_y * 256
            self.img_w = self.diff_x * 256
            self.logger.debug(f"Generating canvas with dimensions {self.img_w}px by {self.img_h}px")
            self.canvas = Image.new(mode="RGB", size=(self.img_w, self.img_h))
            self.status.set('Finished Initial Calculations')
            self.root.update()

            self.urls = []
            self.logger.info("Generating list of URLs to retrieve")
            ZOOM_LEVEL = self.ZOOM_LEVEL.get()
            BASE_URL = self.BASE_URL.get()
            self.status.set('Generating URL List')
            self.root.update()
            for x in range(self.x1, self.x2):
                for y in range(self.y1,self.y2):
                    if self.MAP_TYPE.get() == 'MAPBOX':
                        url = f"{BASE_URL}/{ZOOM_LEVEL}/{x}/{y}.png?access_token={ACCESS_TOKEN}"
                    elif self.MAP_TYPE.get() == 'GOOGLE':
                        # https://khms0.google.com/kh/v=917?x=1&y=1&z=1
                        url = f"{BASE_URL}/v=917?x={x}&y={y}&z={ZOOM_LEVEL}"
                    self.urls.append({'url': url, 'x': x, 'y': y})
            self.logger.info("...DONE!")
            self.loop = asyncio.get_event_loop()
            self.status.set('Fetching Tiles...')
            self.root.update()
            self.received_tiles = 0
            
            self.tiles = self.loop.run_until_complete(self.fetch_all(self.urls,self.loop))
            self.status.set('Got all tiles. Stitching.')
            self.root.update()
            for tile_number, tile in enumerate(self.tiles):
                if (tile_number % math.ceil(self.total_tiles.get()/100) == 0): # 5% progress indicator
                    self.logger.info(f"Stitching tile {tile_number}/{self.total_tiles.get()}")
                    self.status.set(f"Stitching tile {tile_number}/{self.total_tiles.get()}")
                    self.root.update()
                try:
                    bytes_file = io.BytesIO(tile[0])
                    img = Image.open(bytes_file)
                    # img.save(f"{ZOOM_LEVEL}_{x}_{y}.jpg")
                    x = tile[1]
                    y = tile[2]
                    px = (x - self.x1) * 256
                    py = (y - self.y1) * 256
                    self.canvas.paste(img, (px, py))
                except Exception as e:
                    logger.exception(e)
            self.status.set('Finished Stitching, saving')
            self.root.update()
            self.logger.info("Finished Assembling Tiles")
            self.logger.info("Saving Output...")
            filename = f'{self.x1}_{self.y1}_{self.x2}_{self.y2}_{self.MAP_TYPE.get()}_{ZOOM_LEVEL}.jpg'
            self.canvas.save(filename)
            self.logger.info("...Saved Input")
            self.status.set('Finished saving, Done')
            self.root.update()
            self.downloadbutton['state'] = 'normal'
            os.system(filename)
        except Exception as e:
            self.status.set(f"Exception: {e}")
            self.root.update()
            self.downloadbutton['state'] = 'normal'



my_downloader = Map_downloader(-30.402687,136.807408, -30.492760, 136.917227,17,"GOOGLE")