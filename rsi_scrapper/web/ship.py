"""Get ships
"""
import re
import asyncio
from lxml import html

from .connector import Connector
from .interface import ICommand

class Ship(ICommand):
	"""Get ships
	"""

	__url_search_ships = "https://robertsspaceindustries.com/api/store/getShips"
	__url_ships_id = "https://robertsspaceindustries.com/ship-matrix/index"

	def __init__(self, **kwargs):
		self.kwargs = kwargs

	async def execute_async(self):
		return self.execute()

	def execute(self):
		return asyncio.run(self.get_ships_pages_async())

	async def get_ships_pages_async(self):
		"""Get all ships using advanced search through pages.

		Returns:
			list: Ships.
		"""
		name = self.convert_val(self.kwargs.get("name"))
		classification = self.convert_val(self.kwargs.get("classification"))
		length_min = self.convert_val(self.kwargs.get("length_min"))
		length_max = self.convert_val(self.kwargs.get("length_max"))
		crew_min = self.convert_val(self.kwargs.get("crew_min"))
		crew_max = self.convert_val(self.kwargs.get("crew_max"))
		price_min = self.convert_val(self.kwargs.get("price_min"))
		price_max = self.convert_val(self.kwargs.get("price_max"))
		mass_min = self.convert_val(self.kwargs.get("mass_min"))
		mass_max = self.convert_val(self.kwargs.get("mass_max"))
		page = self.convert_val(self.kwargs.get("page"))
		page_max = self.convert_val(self.kwargs.get("page_max"))

		if re.match(r"^\d+?$", str(page)):
			page = int(page)
		else:
			page = 1

		if re.match(r"^\d+?$", page_max):
			page_max = int(page_max)
		else:
			page_max = 1

		data = {
			'classification': classification,
			'itemType': 'ships',
			'length': self.http_formatter(length_min, length_max),
			'manufacturer_id': [],
			'mass': self.http_formatter(mass_min, mass_max),
			'max_crew': self.http_formatter(crew_min, crew_max),
			'msrp': self.http_formatter(price_min, price_max),
			'search': name,
			'page' : page,
			'sort': 'id',
			'storefront': 'pledge',
			'type': '',
		}

		req = Connector().request(self.__url_search_ships, data)

		if req is None or req.status_code == 404:
			return {}
		elif req.status_code != 200:
			return None

		resp = req.json()

		# get html contents
		if resp['success'] != 1:
			return None

		ships = []

		tree = html.fromstring(resp['data']['html'])
		tasks_ship = []
		ships_res = []
		for v in tree.xpath("//*[contains(@class, 'ship-item')]/@data-ship-id"):
			# Create async task
			tasks_ship.append(asyncio.create_task(self.get_ships_async(v.strip())))

		# Wait tasks to finish
		for t in tasks_ship:
			await t
			result = t.result()
			if result is not None:
				ships_res.append(result)

		for resp_ship, req_page in ships_res:
			page_tree = html.fromstring(req_page.content)

			# Get the Ship price
			price = 0
			for price in page_tree.xpath("//*[@class='final-price']/@data-value"):
				price = int(str(price))
				p = int(str(price)) / 100

				if price == 0 or price > p:
					price = p
			resp_ship['price'] = price

			ships.append(resp_ship)

		if resp['data']['rowcount'] != 0 and page < page_max:
			self.kwargs['page'] = page + 1
			val = self.execute(**self.kwargs)
			if val != []:
				ships.extend(val)
		return ships

	async def get_ships_async(self, ship_id: int):
		"""Get ship by its id.

		Args:
			ship_id (int): The ship id.

		Returns:
			dict: The ship.
		"""
		resp_ship = await self.get_ship_by_id(ship_id)
		req_page = None

		if resp_ship is not None:
			req_page = (await asyncio.gather(Connector().request_async(Connector().url_host + resp_ship['url'])))[0]

		if req_page is None or req_page.status_code != 200:
			return None
		return (resp_ship, req_page)

	async def get_ship_by_id(self, ship_id: int = None, get_price=False):
		"""Get a ship by his ship_id.

		Args:
			ship_id (int, optional): The ship ID. Defaults to None.
			get_price (bool, optional): if the price need to be retrieved. Defaults to False.

		Returns:
			[type]: The ship.
		"""

		parameters = {}
		if ship_id is not None:
			parameters = {'id': ship_id}

		req = Connector().request(self.__url_ships_id, parameters)

		if req is None:
			return None
		elif req.status_code == 404:
			return {}
		elif req.status_code != 200:
			return None

		resp_ship = req.json()

		if resp_ship['success'] != 1 or not 'data' in resp_ship or len(resp_ship['data']) == 0:
			return None

		res = []
		if ship_id is None:
			res = resp_ship['data']
		else:
			res = resp_ship['data'][0]

		if get_price:
			for s in res:
				req_page = Connector().request(Connector().url_host + s['url'])

				page_tree = html.fromstring(req_page.content)

				# Get the Ship price
				price = 0
				for v in page_tree.xpath("//*[@class='final-price']/@data-value"):
					p = int(str(v)) / 100

					if price == 0 or price > p:
						price = p
				s['price'] = price

		return res
