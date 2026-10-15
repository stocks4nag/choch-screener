import io, os, time
import requests, pandas as pd, yfinance as yf
from flask import Flask, jsonify, request, Response

app = Flask(__name__)
ACCESS_KEY = os.environ.get("ACCESS_KEY", "")  # optional password for personal use
UA = {"User-Agent": "Mozilla/5.0"}
# --- Built-in stock lists -------------------------------------------------
# niftyindices.com / nseindia.com block requests from cloud servers (Render,
# AWS, etc.) with a 403, even with browser-like headers. To keep this app
# working reliably, the index/sector lists are bundled here instead of being
# fetched live. Composition changes a few times a year - see the note in the
# chat reply for how to refresh this list later.
# Format: symbol -> (Company Name, Industry)

_class NseUtils:
    equity_market_list = ['NIFTY 50', 'NIFTY NEXT 50', 'NIFTY MIDCAP 50', 'NIFTY MIDCAP 100',
                          'NIFTY MIDCAP 150', 'NIFTY SMALLCAP 50', 'NIFTY SMALLCAP 100', 'NIFTY SMALLCAP 250',
                          'NIFTY MIDSMALLCAP 400', 'NIFTY 100', 'NIFTY 200', 'NIFTY AUTO',
                          'NIFTY BANK', 'NIFTY ENERGY', 'NIFTY FINANCIAL SERVICES', 'NIFTY FINANCIAL SERVICES 25/50',
                          'NIFTY FMCG',
                          'NIFTY IT', 'NIFTY MEDIA', 'NIFTY METAL', 'NIFTY PHARMA', 'NIFTY PSU BANK', 'NIFTY REALTY',
                          'NIFTY PRIVATE BANK', 'Securities in F&O', 'Permitted to Trade',
                          'NIFTY DIVIDEND OPPORTUNITIES 50',
                          'NIFTY50 VALUE 20', 'NIFTY100 QUALITY 30', 'NIFTY50 EQUAL WEIGHT', 'NIFTY100 EQUAL WEIGHT',
                          'NIFTY100 LOW VOLATILITY 30', 'NIFTY ALPHA 50', 'NIFTY200 QUALITY 30',
                          'NIFTY ALPHA LOW-VOLATILITY 30',
                          'NIFTY200 MOMENTUM 30', 'NIFTY COMMODITIES', 'NIFTY INDIA CONSUMPTION', 'NIFTY CPSE',
                          'NIFTY INFRASTRUCTURE',
                          'NIFTY MNC', 'NIFTY GROWTH SECTORS 15', 'NIFTY PSE', 'NIFTY SERVICES SECTOR',
                          'NIFTY100 LIQUID 15',
                          'NIFTY MIDCAP LIQUID 15']
    pre_market_list = ['NIFTY 50', 'Nifty Bank', 'Emerge', 'Securities in F&O', 'Others', 'All']

    def __init__(self):

        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.83 Safari/537.36',
            'Upgrade-Insecure-Requests': "1",
            "DNT": "1",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*,q=0.8",
            'Accept-Language': 'en-US,en;q=0.9',
            # 'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        }

        self.session = requests.Session()
        self.session.get("http://nseindia.com", headers=self.headers)
        self.cookies = self.session.cookies.get_dict()

    def pre_market_info(self, category='All'):
        pre_market_xref = {"NIFTY 50": "NIFTY%2050", "Nifty Bank": "NIFTY%20BANK", "Emerge": "SME", "Securities in F&O": "FO",
                           "COMMODITY ETFS": "ETF", "Others": "OTHERS", "All": "ALL"}

        ref_url = 'https://www.nseindia.com/market-data/pre-open-market-cm-and-emerge-market'
        ref = requests.get(ref_url, headers=self.headers)
        url = f"https://www.nseindia.com/api/NextApi/apiClient/cmPreOpenApi?functionName=getPreOpenData&category={pre_market_xref[category]}&symbol="
        response = self.session.get(url, headers=self.headers, cookies=ref.cookies.get_dict())
        processed_data = []
        data = response.json()['data']

        for i in data:
            processed_data.append(i)
        df = pd.DataFrame(processed_data)
        df = df.set_index("symbol", drop=True)
        return df

    def get_index_details(self, category, list_only=False):
        category = category.upper().replace('&', '%26').replace(' ', '%20')

        ref_url = "https://www.nseindia.com/market-data/live-equity-market?symbol={category}"
        ref = requests.get(ref_url, headers=self.headers)
        if category == 'ALL':
            url = f"https://www.nseindia.com/api/allIndices"
            data = requests.get(url, headers=self.headers, cookies=ref.cookies.get_dict()).json()
            df = pd.DataFrame(data['data'])
            df = df.set_index("indexSymbol", drop=True)
        else:
            url = f"https://www.nseindia.com/api/NextApi/apiClient/marketWatchApi?functionName=getIndicesData&symbol={category}"
            data = requests.get(url, headers=self.headers, cookies=ref.cookies.get_dict()).json()
            df = pd.DataFrame(data['data']['data'])
            df = df.set_index("symbol", drop=True)
        if list_only:
            symbol_list = sorted(df.index[1:].tolist())
            return symbol_list
        else:
            return df

    def clearing_holidays(self, list_only=False):
        """
        Returns the list of NSE clearing holidays
        :param list_only: If case of  list_only, the holidays are returned as a simple list. Else
        full details are provided in a dataframe
        :return:
        """
        data = self.session.get(f'https://www.nseindia.com/api/holiday-master?type={'Clearing'.lower()}',
                                headers=self.headers).json()
        df = pd.DataFrame(list(data.values())[0])
        if list_only:
            holiday_list = df['tradingDate'].tolist()
            return holiday_list
        return df

    def trading_holidays(self, list_only=False):
        """
        Returns the list of NSE trading holidays
        :param list_only: If case of  list_only, the holidays are returned as a simple list. Else
        full details are provided in a dataframe
        :return:
        """
        data = self.session.get(f'https://www.nseindia.com/api/holiday-master?type={'Trading'.lower()}',
                                headers=self.headers).json()
        df = pd.DataFrame(list(data.values())[0])
        if list_only:
            holiday_list = df['tradingDate'].tolist()
            return holiday_list
        else:
            return df

    def is_nse_trading_holiday(self, date_str=None):
        """
        Return True if the date supplied in a NSE trading holiday, else False
        :param date_str: Optional. If no date provided, current data will be assumed
        :return:
        """
        holidays = self.trading_holidays(list_only=True)  # Fetch Trading holiday list from NSE

        date_format = "%d-%b-%Y"  # Define the expected date format
        # If date_str is provided, validate and parse it
        if date_str:
            try:
                date_obj = datetime.strptime(date_str, date_format)  # Convert string to datetime
            except ValueError:
                print("Error: Invalid date format! Please use 'DD-MMM-YYYY' (e.g., '19-Feb-2025').")
                return None
        else:
            date_obj = datetime.today()  # Use today's date if no input is given

        formatted_date = date_obj.strftime(date_format)  # Convert date back to the required format
        return formatted_date in holidays  # Check if it’s a holiday

    def is_nse_clearing_holiday(self, date_str=None):
        """
        Return True if the date supplied in a NSE clearing holiday, else False
        :param date_str: Optional. If no date provided, current data will be assumed
        :return:
        """
        holidays = self.clearing_holidays(list_only=True)  # Fetch Trading holiday list from NSE

        date_format = "%d-%b-%Y"  # Define the expected date format
        # If date_str is provided, validate and parse it
        if date_str:
            try:
                date_obj = datetime.strptime(date_str, date_format)  # Convert string to datetime
            except ValueError:
                print("Error: Invalid date format! Please use 'DD-MMM-YYYY' (e.g., '19-Feb-2025').")
                return None
        else:
            date_obj = datetime.today()  # Use today's date if no input is given

        formatted_date = date_obj.strftime(date_format)  # Convert date back to the required format
        return formatted_date in holidays  # Check if it’s a holiday

    def equity_info(self, symbol):
        """
        Extracts the full details of a symbol as see on NSE website
        :param symbol:
        :return:
        """
        symbol = symbol.replace(' ', '%20').replace('&', '%26')

        # Fetch primary details
        ref_url = 'https://www.nseindia.com/get-quotes/equity?symbol=' + symbol
        ref = requests.get(ref_url, headers=self.headers)
        # url = 'https://www.nseindia.com/api/quote-equity?symbol=' + symbol
        url = 'https://www.nseindia.com/api/NextApi/apiClient/GetQuoteApi?functionName=getSymbolData&marketType=N&series=EQ&symbol=' + symbol
        data = requests.get(url, headers=self.headers, cookies=ref.cookies.get_dict()).json()
        # from pprint import pprint
        # pprint(data['equityResponse'][0])
        return data['equityResponse'][0]

    def price_info(self, symbol):
        """
        Gets all key price related information for a given stock
        :param symbol:
        :param trade_info:
        :return:
        """
        symbol = symbol.replace(' ', '%20').replace('&', '%26')
        ref_url = 'https://www.nseindia.com/get-quotes/equity?symbol=' + symbol
        ref = requests.get(ref_url, headers=self.headers)
        url = 'https://www.nseindia.com/api/NextApi/apiClient/GetQuoteApi?functionName=getSymbolData&marketType=N&series=EQ&symbol=' + symbol
        raw_data = requests.get(url, headers=self.headers, cookies=ref.cookies.get_dict()).json()
        data = raw_data['equityResponse'][0]

        if not data:
            return None
        if 'error' in data:
            return None

        return {
            "Symbol": symbol,
            "LastTradedPrice": data['tradeInfo']['lastPrice'],
            "PreviousClose": data['metaData']['previousClose'],
            "Change": data['metaData']['change'],
            "PercentChange": data['metaData']['pChange'],
            "Open": data['metaData']['open'],
            "Close": data['metaData']['closePrice'],
            "High": data['metaData']['dayHigh'],
            "Low": data['metaData']['dayLow'],
            "DeliveryQuantity": data['tradeInfo']['deliveryquantity'],
            "TradedVolume": data['tradeInfo']['totalTradedVolume'],
        }

    def options_data(self, symbol, indices=False):
        """
        Returns the list of futures instruments for a given stock and its  details
        :param symbol:
        :param indices: This is to set to true if symbol is an index
        :return:
        """
        symbol = symbol.replace(' ', '%20').replace('&', '%26')

        ref_url = 'https://www.nseindia.com/get-quotes/derivatives?symbol=' + symbol
        ref = requests.get(ref_url, headers=self.headers)
        url = 'https://www.nseindia.com/api/NextApi/apiClient/GetQuoteApi?functionName=getSymbolDerivativesData&symbol=' + symbol
        symbol_data = self.session.get(url, headers=self.headers, cookies=ref.cookies.get_dict()).json()
        df = pd.DataFrame(symbol_data['data'])
        if indices:
            df = df[df['instrumentType'] == "OPTIDX"]
        else:
            df = df[df['instrumentType']=="OPTSTK"]
        df = df.set_index("identifier", drop=True)
        return df

    def futures_data(self, symbol, indices=False):
        """
        Returns the list of futures instruments for a given stock and its  details
        :param symbol:
        :param indices: This is to set to true if symbol is an index
        :return:
        """
        symbol = symbol.replace(' ', '%20').replace('&', '%26')

        ref_url = 'https://www.nseindia.com/get-quotes/derivatives?symbol=' + symbol
        ref = requests.get(ref_url, headers=self.headers)
        url = 'https://www.nseindia.com/api/NextApi/apiClient/GetQuoteApi?functionName=getSymbolDerivativesData&symbol=' + symbol
        symbol_data = self.session.get(url, headers=self.headers, cookies=ref.cookies.get_dict()).json()
        df = pd.DataFrame(symbol_data['data'])
        if indices:
            df = df[df['instrumentType'] == "FUTIDX"]
        else:
            df = df[df['instrumentType']=="FUTSTK"]
        df = df.set_index("identifier", drop=True)
        return df

    def get_option_chain(self, symbol, expiry, indices=False):
        """
        Returns the full option chain table as seen on NSE website for the given stock/index
        :param symbol:
        :param indices:
        :return:
        """
        df = pd.DataFrame()
        symbol = symbol.replace(' ', '%20').replace('&', '%26')
        if not indices:
            ref_url = 'https://www.nseindia.com/option-chain'
            url = 'https://www.nseindia.com/api/option-chain-v3?type=Equity&symbol=' + symbol + '&expiry=' + expiry
            ref = requests.get(ref_url, headers=self.headers)
            data = self.session.get(url, headers=self.headers, cookies=ref.cookies.get_dict()).json()["records"]
        else:
            ref_url = 'https://www.nseindia.com/option-chain'
            url = 'https://www.nseindia.com/api/option-chain-v3?type=Indices&symbol=' + symbol + '&expiry=' + expiry
            ref = requests.get(ref_url, headers=self.headers)
            data = self.session.get(url, headers=self.headers, cookies=ref.cookies.get_dict()).json()["records"]
        my_df = []

        for i in data["data"]:
            for k, v in i.items():
                if k == "CE" or k == "PE":
                    info = v
                    info["instrumentType"] = k
                    info["timestamp"] = data["timestamp"]
                    my_df.append(info)

        if my_df:
            df = pd.DataFrame(my_df)
            df = df.set_index("identifier", drop=True)
        else:
            print("No Data for input provided")
        return df

    def get_52week_high_low(self, stock=None):
        """
        Get 52 Week High and Low data.  If stock is provided, the High/Low data for that
        particular stock is returned. If not, the  full list is returned
        :param stock: Optional
        :return:
        """
        url = 'https://nsearchives.nseindia.com/content/CM_52_wk_High_low_25012024.csv'

        response = requests.get(url, headers=self.headers)
        data = StringIO(response.text.replace(
            '"Disclaimer - The Data provided in the adjusted 52 week high and adjusted 52 week low columns  are adjusted for corporate actions (bonus, splits & rights).For actual (unadjusted) 52 week high & low prices, kindly refer bhavcopy."\n"Effective for 25-Jan-2024"\n',
            ''))
        df = pd.read_csv(data)
        if stock is not None:
            # Return the full 52 Week High/Low list of stock input
            row = df[df['SYMBOL'] == stock]
            if row.empty:
                return None
            return {
                "Symbol": stock,
                "52 Week High": row["Adjusted 52_Week_High"].values[0],
                "52 Week High Date": row["52_Week_High_Date"].values[0],
                "52 Week Low": row["Adjusted 52_Week_Low"].values[0],
                "52 Week Low Date": row["52_Week_Low_DT"].values[0]
            }
        # Return the full 52 Week High/Low list of all stocks
        return df

    def fno_bhav_copy(self, trade_date: str = ""):
        """
        Get the NSE FNO bhav copy data as per the traded date
        :param trade_date: eg:'20-06-2023'
        :return: pandas data frame
        """
        bhav_df = pd.DataFrame()
        trade_date = datetime.strptime(trade_date, "%d-%m-%Y")
        url = 'https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_'
        payload = f"{str(trade_date.strftime('%Y%m%d'))}_F_0000.csv.zip"
        request_bhav = requests.get(url + payload, headers=self.headers)
        bhav_df = pd.DataFrame()

        if request_bhav.status_code == 200:
            zip_bhav = zipfile.ZipFile(BytesIO(request_bhav.content), 'r')
            for file_name in zip_bhav.filelist:
                if file_name:
                    bhav_df = pd.read_csv(zip_bhav.open(file_name))
        elif request_bhav.status_code == 403:
            url2 = "https://www.nseindia.com/api/reports?archives=" \
                   "%5B%7B%22name%22%3A%22F%26O%20-%20Bhavcopy(csv)%22%2C%22type%22%3A%22archives%22%2C%22category%22" \
                   f"%3A%22derivatives%22%2C%22section%22%3A%22equity%22%7D%5D&date={str(trade_date.strftime('%d-%b-%Y'))}" \
                   f"&type=equity&mode=single"
            request_bhav = requests.get(url2 + payload, headers=self.headers)
            if request_bhav.status_code == 200:
                zip_bhav = zipfile.ZipFile(BytesIO(request_bhav.content), 'r')
                for file_name in zip_bhav.filelist:
                    if file_name:
                        bhav_df = pd.read_csv(zip_bhav.open(file_name))
            elif request_bhav.status_code == 403:
                raise FileNotFoundError(f' Data not found, change the date...')

        return bhav_df

    def bhav_copy_with_delivery(self, trade_date: str):
        """
        Get the NSE bhav copy with delivery data as per the traded date
        :param trade_date: eg:'20-06-2023'
        :return: pandas data frame
        """
        trade_date = datetime.strptime(trade_date, "%d-%m-%Y")
        use_date = trade_date.strftime("%d%m%Y")
        url = f'https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_{use_date}.csv'
        request_bhav = requests.get(url, headers=self.headers)
        if request_bhav.status_code == 200:
            bhav_df = pd.read_csv(BytesIO(request_bhav.content))
        else:
            raise FileNotFoundError(f' Data not found, change the trade_date...')
        bhav_df.columns = [name.replace(' ', '') for name in bhav_df.columns]
        bhav_df['SERIES'] = bhav_df['SERIES'].str.replace(' ', '')
        bhav_df['DATE1'] = bhav_df['DATE1'].str.replace(' ', '')
        return bhav_df

    def equity_bhav_copy(self, trade_date: str):
        """
        Extract Equity Bhav Copy per the traded date provided
        :param trade_date:
        :return: pandas dataframe
        """
        trade_date = datetime.strptime(trade_date, "%d-%m-%Y")
        # trade_date = datetime.strptime(trade_date, dd_mm_yyyy)
        url = 'https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_'
        payload = f"{str(trade_date.strftime('%Y%m%d'))}_F_0000.csv.zip"
        request_bhav = requests.get(url + payload, headers=self.headers)
        bhav_df = pd.DataFrame()
        if request_bhav.status_code == 200:
            zip_bhav = zipfile.ZipFile(BytesIO(request_bhav.content), 'r')
            for file_name in zip_bhav.filelist:
                if file_name:
                    bhav_df = pd.read_csv(zip_bhav.open(file_name))
        elif request_bhav.status_code == 403:
            raise FileNotFoundError(f' Data not found, change the trade_date...')
        return bhav_df

    def bhav_copy_indices(self, trade_date: str):
        """
        Get nse bhav copy as per the traded date provided
        :param trade_date: eg:'20-06-2023'
        :return: pandas dataframe
        """
        trade_date = datetime.strptime(trade_date, "%d-%m-%Y")
        url = f"https://nsearchives.nseindia.com/content/indices/ind_close_all_{str(trade_date.strftime('%d%m%Y').upper())}.csv"
        # nse_resp = nse_urlfetch(url)
        nse_resp = requests.get(url, headers=self.headers)
        if nse_resp.status_code != 200:
            raise FileNotFoundError(f" No data available for : {trade_date}")
        try:
            bhav_df = pd.read_csv(BytesIO(nse_resp.content))
        except Exception as e:
            raise FileNotFoundError(f' Bhav copy indices not found for : {trade_date} :: NSE error : {e}')
        return bhav_df

    def fii_dii_activity(self):
        """
        FII and DII trading activity of the day in data frame
        :return: pd.DataFrame
        """
        url = "https://www.nseindia.com/api/fiidiiTradeReact"
        # data_json = nse_urlfetch(url).json()
        data_json = requests.get(url, headers=self.headers)
        data_df = pd.DataFrame(data_json.json())
        return data_df

    def get_live_option_chain(self, symbol: str, expiry_date: str = None, oi_mode: str = "full", indices=False):
        """
        get live nse option chain.
        :param symbol: eg:SBIN/BANKNIFTY
        :param expiry_date: '20-06-2023'
        :param oi_mode: eg: full/compact
        :return: pands dataframe
        """
        symbol = symbol.replace(' ', '%20').replace('&', '%26')
        ref_url = 'https://www.nseindia.com/option-chain'
        ref = requests.get(ref_url, headers=self.headers)
        if not indices:
            url = 'https://www.nseindia.com/api/option-chain-equities?symbol=' + symbol
        else:
            # ref_url = 'https://www.nseindia.com/option-chain'
            # ref = requests.get(ref_url, headers=self.headers)
            url = 'https://www.nseindia.com/api/option-chain-indices?symbol=' + symbol
        payload = self.session.get(url, headers=self.headers, cookies=ref.cookies.get_dict()).json()
        # payload = get_nse_option_chain(symbol).json()
        if expiry_date:
            exp_date = pd.to_datetime(expiry_date, format='%d-%m-%Y')
            expiry_date = exp_date.strftime('%d-%b-%Y')

        if oi_mode == 'compact':
            col_names = ['Fetch_Time', 'Symbol', 'Expiry_Date', 'CALLS_OI', 'CALLS_Chng_in_OI', 'CALLS_Volume',
                         'CALLS_IV',
                         'CALLS_LTP', 'CALLS_Net_Chng', 'Strike_Price', 'PUTS_OI', 'PUTS_Chng_in_OI', 'PUTS_Volume',
                         'PUTS_IV', 'PUTS_LTP', 'PUTS_Net_Chng']
        else:
            col_names = ['Fetch_Time', 'Symbol', 'Expiry_Date', 'CALLS_OI', 'CALLS_Chng_in_OI', 'CALLS_Volume',
                         'CALLS_IV',
                         'CALLS_LTP', 'CALLS_Net_Chng', 'CALLS_Bid_Qty', 'CALLS_Bid_Price', 'CALLS_Ask_Price',
                         'CALLS_Ask_Qty', 'Strike_Price', 'PUTS_Bid_Qty', 'PUTS_Bid_Price', 'PUTS_Ask_Price',
                         'PUTS_Ask_Qty',
                         'PUTS_Net_Chng', 'PUTS_LTP', 'PUTS_IV', 'PUTS_Volume', 'PUTS_Chng_in_OI', 'PUTS_OI']

        oi_data = pd.DataFrame(columns=col_names)

        oi_row = {'Fetch_Time': None, 'Symbol': None, 'Expiry_Date': None, 'CALLS_OI': 0, 'CALLS_Chng_in_OI': 0,
                  'CALLS_Volume': 0,
                  'CALLS_IV': 0, 'CALLS_LTP': 0, 'CALLS_Net_Chng': 0, 'CALLS_Bid_Qty': 0, 'CALLS_Bid_Price': 0,
                  'CALLS_Ask_Price': 0, 'CALLS_Ask_Qty': 0, 'Strike_Price': 0, 'PUTS_OI': 0, 'PUTS_Chng_in_OI': 0,
                  'PUTS_Volume': 0, 'PUTS_IV': 0, 'PUTS_LTP': 0, 'PUTS_Net_Chng': 0, 'PUTS_Bid_Qty': 0,
                  'PUTS_Bid_Price': 0, 'PUTS_Ask_Price': 0, 'PUTS_Ask_Qty': 0}

        for m in range(len(payload['records']['data'])):
            if not expiry_date or (payload['records']['data'][m]['expiryDate'] == expiry_date):
                try:
                    oi_row['Expiry_Date'] = payload['records']['data'][m]['expiryDate']
                    oi_row['CALLS_OI'] = payload['records']['data'][m]['CE']['openInterest']
                    oi_row['CALLS_Chng_in_OI'] = payload['records']['data'][m]['CE']['changeinOpenInterest']
                    oi_row['CALLS_Volume'] = payload['records']['data'][m]['CE']['totalTradedVolume']
                    oi_row['CALLS_IV'] = payload['records']['data'][m]['CE']['impliedVolatility']
                    oi_row['CALLS_LTP'] = payload['records']['data'][m]['CE']['lastPrice']
                    oi_row['CALLS_Net_Chng'] = payload['records']['data'][m]['CE']['change']
                    if oi_mode == 'full':
                        oi_row['CALLS_Bid_Qty'] = payload['records']['data'][m]['CE']['bidQty']
                        oi_row['CALLS_Bid_Price'] = payload['records']['data'][m]['CE']['bidprice']
                        oi_row['CALLS_Ask_Price'] = payload['records']['data'][m]['CE']['askPrice']
                        oi_row['CALLS_Ask_Qty'] = payload['records']['data'][m]['CE']['askQty']
                except KeyError:
                    oi_row['CALLS_OI'], oi_row['CALLS_Chng_in_OI'], oi_row['CALLS_Volume'], oi_row['CALLS_IV'], oi_row[
                        'CALLS_LTP'], oi_row['CALLS_Net_Chng'] = 0, 0, 0, 0, 0, 0
                    if oi_mode == 'full':
                        oi_row['CALLS_Bid_Qty'], oi_row['CALLS_Bid_Price'], oi_row['CALLS_Ask_Price'], oi_row[
                            'CALLS_Ask_Qty'] = 0, 0, 0, 0
                    pass

                oi_row['Strike_Price'] = payload['records']['data'][m]['strikePrice']

                try:
                    oi_row['PUTS_OI'] = payload['records']['data'][m]['PE']['openInterest']
                    oi_row['PUTS_Chng_in_OI'] = payload['records']['data'][m]['PE']['changeinOpenInterest']
                    oi_row['PUTS_Volume'] = payload['records']['data'][m]['PE']['totalTradedVolume']
                    oi_row['PUTS_IV'] = payload['records']['data'][m]['PE']['impliedVolatility']
                    oi_row['PUTS_LTP'] = payload['records']['data'][m]['PE']['lastPrice']
                    oi_row['PUTS_Net_Chng'] = payload['records']['data'][m]['PE']['change']
                    if oi_mode == 'full':
                        oi_row['PUTS_Bid_Qty'] = payload['records']['data'][m]['PE']['bidQty']
                        oi_row['PUTS_Bid_Price'] = payload['records']['data'][m]['PE']['bidprice']
                        oi_row['PUTS_Ask_Price'] = payload['records']['data'][m]['PE']['askPrice']
                        oi_row['PUTS_Ask_Qty'] = payload['records']['data'][m]['PE']['askQty']
                except KeyError:
                    oi_row['PUTS_OI'], oi_row['PUTS_Chng_in_OI'], oi_row['PUTS_Volume'], oi_row['PUTS_IV'], oi_row[
                        'PUTS_LTP'], oi_row['PUTS_Net_Chng'] = 0, 0, 0, 0, 0, 0
                    if oi_mode == 'full':
                        oi_row['PUTS_Bid_Qty'], oi_row['PUTS_Bid_Price'], oi_row['PUTS_Ask_Price'], oi_row[
                            'PUTS_Ask_Qty'] = 0, 0, 0, 0

                if oi_data.empty:
                    oi_data = pd.DataFrame([oi_row]).copy()
                else:
                    oi_data = pd.concat([oi_data, pd.DataFrame([oi_row])], ignore_index=True)
                oi_data['Symbol'] = symbol
                oi_data['Fetch_Time'] = payload['records']['timestamp']
        return oi_data

    def get_market_depth(self, symbol):

        """
        Function to retrieve market depth for a given symbol
        :param symbol:
        :return: Market Dept as Dict
        """
        data = self.equity_info(symbol)
        order_book = data["orderBook"]
        levels = []
        for i in range(1, 6):
            levels.append({
                "level": i,
                "bid_price": order_book[f"buyPrice{i}"],
                "bid_quantity": order_book[f"buyQuantity{i}"],
                "ask_price": order_book[f"sellPrice{i}"],
                "ask_quantity": order_book[f"sellQuantity{i}"]
            })

        return levels

    def get_index_historic_data(self, index: str, from_date: str = None, to_date: str = None):
        """
        get historical index data set for the specific time period.
        apply the index name as per the nse india site
        :param index: 'NIFTY 50'/'NIFTY BANK'
        :param from_date: '17-03-2022' ('dd-mm-YYYY')
        :param to_date: '17-06-2023' ('dd-mm-YYYY')
        :return: pandas.DataFrame
        :raise ValueError if the parameter input is not proper
        """
        index_data_columns = ['TIMESTAMP', 'INDEX_NAME', 'OPEN_INDEX_VAL', 'HIGH_INDEX_VAL', 'CLOSE_INDEX_VAL',
                              'LOW_INDEX_VAL', 'TRADED_QTY', 'TURN_OVER']

        # Check for valid dates and period inputs
        if not from_date or not to_date:
            raise ValueError(' Please provide the valid parameters')

        try:
            from_dt = datetime.strptime(from_date, "%d-%m-%Y")
            to_dt = datetime.strptime(to_date, "%d-%m-%Y")
            time_delta = (to_dt - from_dt).days
            if time_delta < 1:
                raise ValueError(f'to_date should greater than from_date ')
        except Exception as e:
            print(e)
            raise ValueError(f'either or both from_date = {from_date} || to_date = {to_date} are not valid value')

        nse_df = pd.DataFrame(columns=index_data_columns)
        from_date = datetime.strptime(from_date, "%d-%m-%Y")
        to_date = datetime.strptime(to_date, "%d-%m-%Y")
        load_days = (to_date - from_date).days

        while load_days > 0:
            if load_days > 365:
                end_date = (from_date + timedelta(364)).strftime("%d-%m-%Y")
                start_date = from_date.strftime("%d-%m-%Y")
            else:
                end_date = to_date.strftime("%d-%m-%Y")
                start_date = from_date.strftime("%d-%m-%Y")

            data_df = self.get_index_data(index=index, from_date=start_date, to_date=end_date)
            from_date = from_date + timedelta(365)
            load_days = (to_date - from_date).days
            if nse_df.empty:
                nse_df = data_df
            else:
                nse_df = pd.concat([nse_df, data_df], ignore_index=True)
        return nse_df

    def get_index_data(self, index: str, from_date: str, to_date: str):

        index_data_columns = ['TIMESTAMP', 'INDEX_NAME', 'OPEN_INDEX_VAL', 'HIGH_INDEX_VAL', 'CLOSE_INDEX_VAL',
                              'LOW_INDEX_VAL', 'TRADED_QTY', 'TURN_OVER']

        index = index.replace(' ', '%20').upper()
        ref_url = 'https://www.nseindia.com/reports-indices-historical-index-data'
        ref = requests.get(ref_url, headers=self.headers)

        url = f"https://www.nseindia.com/api/historical/indicesHistory?indexType={index}&from={from_date}&to={to_date}"
        print(url)
        data_json = self.session.get(url, headers=self.headers, cookies=ref.cookies.get_dict()).json()
        print("teat", data_json)
        try:
            data_json = self.session.get(url, headers=self.headers, cookies=ref.cookies.get_dict()).json()
            print("teat" , data_json)
            data_close_df = pd.DataFrame(data_json['data']['indexCloseOnlineRecords']).drop(
                columns=['_id', "EOD_TIMESTAMP"])
            data_turnover_df = pd.DataFrame(data_json['data']['indexTurnoverRecords']).drop(columns=['_id',
                                                                                                     'HIT_INDEX_NAME_UPPER'])
            data_df = pd.merge(data_close_df, data_turnover_df, on='TIMESTAMP', how='inner')
        except Exception as e:
            raise " Resource not available"

        data_df.drop(columns='TIMESTAMP', inplace=True)

        unwanted_str_list = ['FH_', 'EOD_', 'HIT_']
        new_col = data_df.columns
        for unwanted in unwanted_str_list:
            new_col = [name.replace(f'{unwanted}', '') for name in new_col]

        data_df.columns = new_col
        return data_df[index_data_columns]

    def get_equity_full_list(self, list_only=False):
        """
        get list of all equity available to trade in NSE
        :param list_only: Optional. If you only need the symbols in a list, set this to true.
        Otherwise, the full table is downloaded as a dataframe
        :return: pandas data frame
        """
        url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
        nse_resp = self.session.get(url, headers=self.headers, cookies=self.cookies)
        if nse_resp.status_code != 200:
            raise FileNotFoundError(f" No data equity list available")
        try:
            data_df = pd.read_csv(BytesIO(nse_resp.content))
        except Exception as e:
            raise FileNotFoundError(f' Equity List not found :: NSE error : {e}')
        data_df = data_df[['SYMBOL', 'NAME OF COMPANY', ' SERIES', ' DATE OF LISTING', ' FACE VALUE']]
        if list_only:
            symbol_list = data_df['SYMBOL'].tolist()
            return symbol_list
        return data_df

    def get_fno_full_list(self, list_only=False):
        """
        get a dataframe of all listed derivative list with the recent lot size to trade
        :param list_only: Optional. If you only need the symbols in a list, set this to true.
        Otherwise, the full table is downloaded as a dataframe
        :return: pandas data frame
        """
        ref_url = 'https://www.nseindia.com/products-services/equity-derivatives-list-underlyings-information'
        ref = requests.get(ref_url, headers=self.headers)
        url = "https://www.nseindia.com/api/underlying-information"
        response = requests.get(url, headers=self.headers, cookies=ref.cookies.get_dict())

        if response.status_code != 200:
            raise ("Resource not available for fno_equity_list")
        data_dict = response.json()
        data_df = pd.DataFrame(data_dict['data']['UnderlyingList'])
        if list_only:
            symbol_list = data_df['symbol'].tolist()
            return symbol_list
        return data_df

    def get_gainers_losers(self):

        gain_loss_dict = {}

        ref_url = 'https://www.nseindia.com/market-data/top-gainers-losers'
        ref = requests.get(ref_url, headers=self.headers)

        url = 'https://www.nseindia.com/api/live-analysis-variations?index=gainers'
        data_obj = requests.get(url, headers=self.headers, cookies=ref.cookies.get_dict())
        if data_obj.status_code != 200:
            raise ("Resource not available for fno_equity_list")
        data_dict = data_obj.json()

        # Nifty Gainer
        data_df = pd.DataFrame(data_dict['NIFTY']['data'])
        if not data_df.empty:
            nifty_gainer = data_df['symbol'].to_list()
        else:
            nifty_gainer = []

        # Bank Nifty Gainer
        data_df = pd.DataFrame(data_dict['BANKNIFTY']['data'])
        if not data_df.empty:
            banknifty_gainer = data_df['symbol'].to_list()
        else:
            banknifty_gainer = []

        # Nifty Next 50 Gainer
        data_df = pd.DataFrame(data_dict['NIFTYNEXT50']['data'])
        if not data_df.empty:
            next50_gainer = data_df['symbol'].to_list()
        else:
            next50_gainer = []

        # All Securities Gainer
        data_df = pd.DataFrame(data_dict['allSec']['data'])
        if not data_df.empty:
            allsec_gainer = data_df['symbol'].to_list()
        else:
            allsec_gainer = []

        # FNO Securities Gainer
        data_df = pd.DataFrame(data_dict['FOSec']['data'])
        if not data_df.empty:
            fno_gainer = data_df['symbol'].to_list()
        else:
            fno_gainer = []

        url = 'https://www.nseindia.com/api/live-analysis-variations?index=loosers'
        data_obj = self.session.get(url, headers=self.headers, cookies=ref.cookies.get_dict())
        if data_obj.status_code != 200:
            raise ("Resource not available for fno_equity_list")
        data_dict = data_obj.json()

        # Nifty Gainer
        data_df = pd.DataFrame(data_dict['NIFTY']['data'])
        if not data_df.empty:
            nifty_loser = data_df['symbol'].to_list()
        else:
            nifty_loser = []

        # Bank Nifty Gainer
        data_df = pd.DataFrame(data_dict['BANKNIFTY']['data'])
        if not data_df.empty:
            banknifty_loser = data_df['symbol'].to_list()
        else:
            banknifty_loser = []

        # Bank Nifty Gainer
        data_df = pd.DataFrame(data_dict['NIFTYNEXT50']['data'])
        if not data_df.empty:
            next50_loser = data_df['symbol'].to_list()
        else:
            next50_loser = []

        # All Securities Gainer
        data_df = pd.DataFrame(data_dict['allSec']['data'])
        if not data_df.empty:
            allsec_loser = data_df['symbol'].to_list()
        else:
            allsec_loser = []

            # FNO Securities Gainer
        data_df = pd.DataFrame(data_dict['FOSec']['data'])
        if not data_df.empty:
            fno_loser = data_df['symbol'].to_list()
        else:
            fno_loser = []

        gain_dict = {
            'Nifty Gainer': nifty_gainer,
            'Bank Nifty Gainer': banknifty_gainer,
            'Nifty Next 50 Gainer': next50_gainer,
            'All Securities Gainer': allsec_gainer,
            'FNO Gainer': fno_gainer
        }

        loss_dict = {
            'Nifty Loser': nifty_loser,
            'Bank Nifty Loser': banknifty_loser,
            'Nifty Next 50 Loser': next50_loser,
            'All Securities Loser': allsec_loser,
            'FNO Loser': fno_loser
        }

        return gain_dict, loss_dict

    def get_corporate_action(self, from_date_str: str = None, to_date_str: str = None, filter: str = None):

        # Fetch Corporate Action data from NSE
        if from_date_str is None:
            from_date  = datetime.now() - timedelta(days=30)
            from_date_str = from_date.strftime("%d-%m-%Y")
            to_date_str = datetime.now().strftime("%d-%m-%Y")
        if to_date_str is None:
            to_date_str = datetime.now().strftime("%d-%m-%Y")

        try:
            ref_url = 'https://www.nseindia.com/companies-listing/corporate-filings-actions'
            ref = requests.get(ref_url, headers=self.headers)
            url = f"https://www.nseindia.com/api/corporates-corporateActions?index=equities&from_date={from_date_str}&to_date={to_date_str}"
            data_obj = self.session.get(url, headers=self.headers, cookies=ref.cookies.get_dict())
            corp_action = pd.DataFrame(data_obj.json())
            if filter is not None:
                corp_action = corp_action[corp_action['subject'].str.contains(filter, case=False, na=False)]
            return corp_action
        except:
            print("Error fetching Corporate Action Data. Check your input")
            return None

    def get_corporate_announcement(self, from_date_str: str = None, to_date_str: str = None):

        # Fetch Corporate Announcements data from NSE
        if from_date_str is None:
            from_date  = datetime.now() - timedelta(days=30)
            from_date_str = from_date.strftime("%d-%m-%Y")
            to_date_str = datetime.now().strftime("%d-%m-%Y")
        if to_date_str is None:
            to_date_str = datetime.now().strftime("%d-%m-%Y")

        try:
            ref_url = ('https://www.nseindia.com/companies-listing/corporate-filings-announcements')
            ref = requests.get(ref_url, headers=self.headers)
            url = f'https://www.nseindia.com/api/corporate-announcements?index=equities&from_date={from_date_str}&to_date={to_date_str}'
            data_obj = self.session.get(url, headers=self.headers, cookies=ref.cookies.get_dict())
            corp_announcement = pd.DataFrame(data_obj.json())
            return corp_announcement
        except:
            print("Error fetching Corporate Action Data. Check your input")
            return None

    def get_index_pe_ratio(self):

        # try:
            ref_url = 'https://www.nseindia.com/market-data/index-performances'
            ref = requests.get(ref_url, headers=self.headers)
            url = 'https://www.nseindia.com/api/allIndices'
            response = self.session.get(url, headers=self.headers, cookies=ref.cookies.get_dict())
            data = response.json()  # Convert response to JSON

            # Convert JSON data to a DataFrame
            df = pd.json_normalize(data['data'])  # Extract the main data list

            # Retain only PE Ratio
            if not df.empty:
                df = df[['indexSymbol', 'key', 'pe']]
                df = df[df['pe'].str.strip() != '']  # Removes rows where PE is an empty string
                df = df[df['pe'].str.strip() != 'None']  # Removes rows where PE is none
                df.columns = ['Index', 'Type', 'Profit Earning Ratio']
                return df
            else:
                return None

        # except:
        #     print("Error fetching Corporate Action Data. Check your input")
        #     return None

    def get_index_pb_ratio(self):

        try:
            ref_url = 'https://www.nseindia.com/market-data/index-performances'
            ref = requests.get(ref_url, headers=self.headers)
            url = 'https://www.nseindia.com/api/allIndices'
            response = self.session.get(url, headers=self.headers, cookies=ref.cookies.get_dict())
            data = response.json()  # Convert response to JSON

            # Convert JSON data to a DataFrame
            df = pd.json_normalize(data['data'])  # Extract the main data list

            # Retain only PE Ratio
            if not df.empty:
                df = df[['indexSymbol', 'key', 'pb']]
                df = df[df['pb'].str.strip() != '']  # Removes rows where PE is an empty string
                df = df[df['pb'].str.strip() != 'None']  # Removes rows where PE is none
                df.columns = ['Index', 'Type', 'Price Book Ratio']
                return df
            else:
                return None

        except:
            print("Error fetching Corporate Action Data. Check your input")
            return None

    def get_index_div_yield(self):

        try:
            ref_url = 'https://www.nseindia.com/market-data/index-performances'
            ref = requests.get(ref_url, headers=self.headers)
            url = 'https://www.nseindia.com/api/allIndices'
            response = self.session.get(url, headers=self.headers, cookies=ref.cookies.get_dict())
            data = response.json()  # Convert response to JSON

            # Convert JSON data to a DataFrame
            df = pd.json_normalize(data['data'])  # Extract the main data list

            # Retain only PE Ratio
            if not df.empty:
                df = df[['indexSymbol', 'key', 'dy']]
                df = df[df['dy'].str.strip() != '']  # Removes rows where PE is an empty string
                df = df[df['dy'].str.strip() != 'None']  # Removes rows where PE is none
                df.columns = ['Index', 'Type', 'Div Yield']
                return df
            else:
                return None

        except:
            print("Error fetching Corporate Action Data. Check your input")
            return None

    def get_advance_decline(self):

        try:
            ref_url = 'https://www.nseindia.com/market-data/live-market-indices'
            ref = requests.get(ref_url, headers=self.headers)
            url = 'https://www.nseindia.com/api/allIndices'
            response = self.session.get(url, headers=self.headers, cookies=ref.cookies.get_dict())
            data = response.json()  # Convert response to JSON

            # Convert JSON data to a DataFrame
            df = pd.json_normalize(data['data'])  # Extract the main data list

            # Retain only PE Ratio
            if not df.empty:
                df = df[['indexSymbol', 'advances', 'declines', 'unchanged']]
                df.dropna(inplace=True)
                df.columns = ['Index', 'Advances', 'Declines', 'Unchanged']
                return df
            else:
                return None

        except Exception as e:
            print("Error fetching Corporate Action Data. Check your input")
            return None

    def most_active_equity_stocks_by_volume(self):
        try:
            ref_url = 'https://www.nseindia.com/market-data/most-active-equities'
            ref = requests.get(ref_url, headers=self.headers)
            url = 'https://www.nseindia.com/api/live-analysis-most-active-securities?index=volume'
            response = self.session.get(url, headers=self.headers, cookies=ref.cookies.get_dict())

            data = response.json()  # Convert response to JSON

            # Convert JSON data to a DataFrame
            df = pd.DataFrame(data['data'])  # Extract the main data list

            if df.empty:
                return None
            else:
                return df
        except Exception as e:
            print("Error fetching Corporate Action Data. Check your input")
            return None

    def most_active_equity_stocks_by_value(self):
        try:
            ref_url = 'https://www.nseindia.com/market-data/most-active-equities'
            ref = requests.get(ref_url, headers=self.headers)
            url = 'https://www.nseindia.com/api/live-analysis-most-active-securities?index=value'
            response = self.session.get(url, headers=self.headers, cookies=ref.cookies.get_dict())

            data = response.json()  # Convert response to JSON

            # Convert JSON data to a DataFrame
            df = pd.DataFrame(data['data'])  # Extract the main data list

            if df.empty:
                return None
            else:
                return df
        except Exception as e:
            print("Error fetching Corporate Action Data. Check your input")
            return None

    def most_active_index_calls(self):

        try:
            ref_url = 'https://www.nseindia.com/market-data/most-active-contracts'
            ref = requests.get(ref_url, headers=self.headers)
            url = 'https://www.nseindia.com/api/snapshot-derivatives-equity?index=calls-index-vol'
            response = self.session.get(url, headers=self.headers, cookies=ref.cookies.get_dict())

            data = response.json()  # Convert response to JSON
            # Convert JSON data to a DataFrame
            df = pd.DataFrame(data['OPTIDX']['data'])  # Extract the main data list

            if df.empty:
                return None
            else:
                return df
        except Exception as e:
            print("Error fetching Corporate Action Data. Check your input")
            return None

    def most_active_index_puts(self):

        try:
            ref_url = 'https://www.nseindia.com/market-data/most-active-contracts'
            ref = requests.get(ref_url, headers=self.headers)
            url = 'https://www.nseindia.com/api/snapshot-derivatives-equity?index=puts-index-vol'
            response = self.session.get(url, headers=self.headers, cookies=ref.cookies.get_dict())

            data = response.json()  # Convert response to JSON
            # Convert JSON data to a DataFrame
            df = pd.DataFrame(data['OPTIDX']['data'])  # Extract the main data list

            if df.empty:
                return None
            else:
                return df
        except Exception as e:
            print("Error fetching Corporate Action Data. Check your input")
            return None

    def most_active_stock_calls(self):

        try:
            ref_url = 'https://www.nseindia.com/market-data/most-active-contracts'
            ref = requests.get(ref_url, headers=self.headers)
            url = 'https://www.nseindia.com/api/snapshot-derivatives-equity?index=calls-stocks-vol'
            response = self.session.get(url, headers=self.headers, cookies=ref.cookies.get_dict())

            data = response.json()  # Convert response to JSON
            # Convert JSON data to a DataFrame
            df = pd.DataFrame(data['OPTSTK']['data'])  # Extract the main data list

            if df.empty:
                return None
            else:
                return df
        except Exception as e:
            print("Error fetching Corporate Action Data. Check your input")
            return None

    def most_active_stock_puts(self):

        try:
            ref_url = 'https://www.nseindia.com/market-data/most-active-contracts'
            ref = requests.get(ref_url, headers=self.headers)
            url = 'https://www.nseindia.com/api/snapshot-derivatives-equity?index=puts-stocks-vol'
            response = self.session.get(url, headers=self.headers, cookies=ref.cookies.get_dict())

            data = response.json()  # Convert response to JSON
            # Convert JSON data to a DataFrame
            df = pd.DataFrame(data['OPTSTK']['data'])  # Extract the main data list

            if df.empty:
                return None
            else:
                return df
        except Exception as e:
            print("Error fetching Corporate Action Data. Check your input")
            return None

    def most_active_contracts_by_oi(self):

        try:
            ref_url = 'https://www.nseindia.com/market-data/most-active-contracts'
            ref = requests.get(ref_url, headers=self.headers)
            url = 'https://www.nseindia.com/api/snapshot-derivatives-equity?index=oi'
            response = self.session.get(url, headers=self.headers, cookies=ref.cookies.get_dict())

            data = response.json()  # Convert response to JSON
            # Convert JSON data to a DataFrame
            df = pd.DataFrame(data['volume']['data'])  # Extract the main data list

            if df.empty:
                return None
            else:
                return df
        except Exception as e:
            print("Error fetching Corporate Action Data. Check your input")
            return None

    def most_active_contracts_by_volume(self):

        try:
            ref_url = 'https://www.nseindia.com/market-data/most-active-contracts'
            ref = requests.get(ref_url, headers=self.headers)
            url = 'https://www.nseindia.com/api/snapshot-derivatives-equity?index=contracts'
            response = self.session.get(url, headers=self.headers, cookies=ref.cookies.get_dict())

            data = response.json()  # Convert response to JSON
            # Convert JSON data to a DataFrame
            df = pd.DataFrame(data['volume']['data'])  # Extract the main data list

            if df.empty:
                return None
            else:
                return df
        except Exception as e:
            print("Error fetching Corporate Action Data. Check your input")
            return None

    def most_active_futures_contracts_by_volume(self):

        try:
            ref_url = 'https://www.nseindia.com/market-data/most-active-contracts'
            ref = requests.get(ref_url, headers=self.headers)
            url = 'https://www.nseindia.com/api/snapshot-derivatives-equity?index=futures'
            response = self.session.get(url, headers=self.headers, cookies=ref.cookies.get_dict())

            data = response.json()  # Convert response to JSON
            # Convert JSON data to a DataFrame
            df = pd.DataFrame(data['volume']['data'])  # Extract the main data list

            if df.empty:
                return None
            else:
                return df
        except Exception as e:
            print("Error fetching Corporate Action Data. Check your input")
            return None

    def most_active_options_contracts_by_volume(self):

        try:
            ref_url = 'https://www.nseindia.com/market-data/most-active-contracts'
            ref = requests.get(ref_url, headers=self.headers)
            url = 'https://www.nseindia.com/api/snapshot-derivatives-equity?index=options&limit=20'
            response = self.session.get(url, headers=self.headers, cookies=ref.cookies.get_dict())
            data = response.json()  # Convert response to JSON
            # Convert JSON data to a DataFrame
            df = pd.DataFrame(data['volume']['data'])  # Extract the main data list

            if df.empty:
                return None
            else:
                return df
        except Exception as e:
            print("Error fetching Corporate Action Data. Check your input")
            return None

    def get_insider_trading(self, from_date: str = None, to_date: str = None):

        try:

            if from_date is None:
                from_date  = datetime.now() - timedelta(days=30)
                from_date_str = from_date.strftime("%d-%m-%Y")
                to_date_str = datetime.now().strftime("%d-%m-%Y")
            else:
                from_date_str = from_date
            if to_date is None:
                to_date_str = datetime.now().strftime("%d-%m-%Y")
            else:
                to_date_str = to_date

            ref_url = 'https://www.nseindia.com/companies-listing/corporate-filings-insider-trading'
            ref = requests.get(ref_url, headers=self.headers)
            url= f'https://www.nseindia.com/api/corporates-pit-gg?index=equities&from_date={from_date_str}&to_date={to_date_str}'
            response = requests.get(url, headers=self.headers, cookies=ref.cookies.get_dict())
            data = response.json()
            df = pd.DataFrame(data['data'])

            return df

        except Exception as e:
            print("Error fetching Corporate Action Data. Check your input")
            return None

    def get_upcoming_results_calendar(self):

        # Extracts the events calendar from NSE - Filters only the upcoming Financial results related events
        try:
            ref_url = 'https://www.nseindia.com/companies-listing/corporate-filings-event-calendar'
            ref = requests.get(ref_url, headers=self.headers)
            url= f'https://www.nseindia.com/api/event-calendar?'
            response = requests.get(url, headers=self.headers, cookies=ref.cookies.get_dict())
            data = response.json()
            df = pd.DataFrame(data)
            events = df[df['purpose'].str.contains('Results', case=False, na=False)]
            return events
        except:
            print("Error fetching Corporate Action Data. Check your input")
            return None

    def get_etf_list(self):

        try:
            ref_url = 'https://www.nseindia.com/market-data/exchange-traded-funds-etf'
            ref = requests.get(ref_url, headers=self.headers)
            url = 'https://www.nseindia.com/api/etf'
            response = self.session.get(url, headers=self.headers, cookies=ref.cookies.get_dict())
            data = response.json()  # Convert response to JSON
            # Convert JSON data to a DataFrame
            df = pd.DataFrame(data['data'])  # Extract the main data list

            if df.empty:
                return None
            else:
                return df
        except Exception as e:
            print("Error fetching ETF list. Check your input")
            return None


    def change_in_oi(self):
        try:
            # Change in OI by Underlying
            ref_url = 'https://www.nseindia.com/market-data/oi-spurts'
            ref = requests.get(ref_url, headers=self.headers)
            url = 'https://www.nseindia.com/api/live-analysis-oi-spurts-underlyings'
            response = self.session.get(url, headers=self.headers, cookies=ref.cookies.get_dict())
            data = response.json()  # Convert response to JSON
            # Convert JSON data to a DataFrame
            oi_underlying = pd.DataFrame(data['data'])  # Extract the main data list

            # Change in OI by Contracts
            ref_url = 'https://www.nseindia.com/market-data/oi-spurts'
            ref = requests.get(ref_url, headers=self.headers)
            url = 'https://www.nseindia.com/api/live-analysis-oi-spurts-contracts'
            response = self.session.get(url, headers=self.headers, cookies=ref.cookies.get_dict())
            data = response.json()  # Convert response to JSON
            rows = []

            for item in data["data"]:
                for bucket, values in item.items():
                    for row in values:
                        row["oi_bucket"] = bucket
                        rows.append(row)

            df_all = pd.DataFrame(rows)

            # Change in OI By Contract - Rise in OI Rise in Price
            rise_oi_rise_price =  df_all[df_all["oi_bucket"] == "Rise-in-OI-Rise"]

            # # Change in OI By Contract - Rise in OI Slide in Price
            rise_oi_slide_price = df_all[df_all["oi_bucket"] == "Rise-in-OI-Slide"]

            # Change in OI By Contract - Slide in OI Slide in Price
            slide_oi_slide_price = df_all[df_all["oi_bucket"] == "Slide-in-OI-Slide"]

            # Change in OI By Contract - Slide in OI Rise in Price
            slide_oi_rise_price = df_all[df_all["oi_bucket"] == "Slide-in-OI-Rise"]

            return oi_underlying, rise_oi_rise_price, rise_oi_slide_price, slide_oi_slide_price, slide_oi_rise_price

        except Exception as e:
            print("Error fetching ETF list. Check your input")
            return None


    def change_in_oi_by_contract(self):
        try:
            ref_url = 'https://www.nseindia.com/market-data/oi-spurts'
            ref = requests.get(ref_url, headers=self.headers)
            url = 'https://www.nseindia.com/api/live-analysis-oi-spurts-contracts'
            response = self.session.get(url, headers=self.headers, cookies=ref.cookies.get_dict())
            data = response.json()  # Convert response to JSON
            # Convert JSON data to a DataFrame
            df = pd.DataFrame(data['data'])  # Extract the main data list

            if df.empty:
                return None
            else:
                return df
        except Exception as e:
            print("Error fetching ETF list. Check your input")
            return None


def cached(key, ttl, fn):
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    val = fn()
    _cache[key] = (time.time(), val)
    return val


def load_group(name):
    d = GROUPS[name]
    rows = [(nm, ind, sym) for sym, (nm, ind) in d.items()]
    return pd.DataFrame(rows, columns=["Company Name", "Industry", "Symbol"])


def analyze(d, n):
    """Swing-pivot market structure. BOS = close beyond last swing in trend direction
    (sets a protected level). CHoCH = close beyond that protected level (trend flips)."""
    h, l, c = d["High"].values, d["Low"].values, d["Close"].values
    idx = d.index
    lastH = lastL = None
    trend, prot, bos_bar, ev = 0, None, None, None
    for t in range(len(c)):
        p = t - n
        if p >= n:
            if h[p] == max(h[p - n:p + n + 1]): lastH = (h[p], p)
            if l[p] == min(l[p - n:p + n + 1]): lastL = (l[p], p)
        if trend >= 0 and lastH and c[t] > lastH[0]:      # bullish BOS
            trend, bos_bar = 1, t
            prot = lastL[0] if lastL else None
            lastH = None
        elif trend <= 0 and lastL and c[t] < lastL[0]:    # bearish BOS
            trend, bos_bar = -1, t
            prot = lastH[0] if lastH else None
            lastL = None
        elif trend == 1 and prot is not None and c[t] < prot and bos_bar is not None:
            ev = ("Bearish CHoCH", t, prot, bos_bar)
            trend, prot, lastL = -1, lastH[0] if lastH else None, None
        elif trend == -1 and prot is not None and c[t] > prot and bos_bar is not None:
            ev = ("Bullish CHoCH", t, prot, bos_bar)
            trend, prot, lastH = 1, lastL[0] if lastL else None, None
    if not ev:
        return None
    k, t, lvl, b = ev
    return dict(event=k, bars_ago=len(c) - 1 - t, level=round(float(lvl), 2),
                bos_ago=t - b, close=round(float(c[-1]), 2), time=str(idx[t])[:16])


def swing_points(d, n):
    """All confirmed swing highs/lows using the same pivot rule as analyze() -
    a bar whose High/Low is the max/min of the n bars on each side of it."""
    h, l = d["High"].values, d["Low"].values
    idx = d.index
    out = []
    for t in range(n, len(h) - n):
        if h[t] == max(h[t - n:t + n + 1]):
            out.append({"time": int(pd.Timestamp(idx[t]).timestamp()), "price": round(float(h[t]), 2), "type": "H"})
        if l[t] == min(l[t - n:t + n + 1]):
            out.append({"time": int(pd.Timestamp(idx[t]).timestamp()), "price": round(float(l[t]), 2), "type": "L"})
    return sorted(out, key=lambda r: r["time"])


def fetch(tickers, tf):
    interval, period = TF[tf]
    out = {}
    for i in range(0, len(tickers), 100):
        chunk = tickers[i:i + 100]
        try:
            data = yf.download(chunk, interval=interval, period=period, group_by="ticker",
                               auto_adjust=False, threads=True, progress=False)
        except Exception:
            continue
        # yfinance's column shape depends on the ACTUAL data returned, not on how many
        # tickers were requested (a chunk of 1 can still come back multi-indexed) - so we
        # check the real structure instead of assuming based on len(chunk).
        multi = isinstance(data.columns, pd.MultiIndex)
        for t in chunk:
            try:
                d = data[t] if multi else data
                d = d.dropna(subset=["Close"])
                if tf == "4h":
                    d = d.resample("4h").agg({"Open": "first", "High": "max", "Low": "min",
                                              "Close": "last"}).dropna()
                if len(d) > 30: out[t] = d
            except Exception:
                pass
    return out


@app.before_request
def guard():
    if ACCESS_KEY and request.path.startswith("/api") and request.headers.get("X-Key") != ACCESS_KEY:
        return jsonify(error="Wrong access key"), 401


@app.route("/api/meta")
def meta():
    gi = {g: sorted({v[1] for v in d.values()}) for g, d in GROUPS.items()}
    inds = sorted({v[1] for g in GROUPS.values() for v in g.values()})
    return jsonify(groups=list(GROUPS) + [NIFTY500_LABEL, CUSTOM_LABEL], industries=inds,
                   group_industries=gi, custom_label=CUSTOM_LABEL, nifty500_label=NIFTY500_LABEL)


@app.route("/api/scan")
def scan():
    a = request.args
    ex, grp, ind = a.get("exchange", "NSE"), a.get("group", "Nifty 50 (Large cap)"), a.get("industry", "")
    tf, want = a.get("tf", "1d"), a.get("type", "both")
    within, n = int(a.get("within", 3)), int(a.get("swing", 3))
    if grp in PASTE_GROUPS:
        raw = a.get("symbols", "")
        syms, names_, inds_ = [], [], []
        for line in raw.replace("\r", "").split("\n"):
            line = line.strip()
            if not line: continue
            parts = [p.strip() for p in (line.split("\t") if "\t" in line else line.split(","))]
            sym = parts[0].upper().strip()
            # strip common suffixes people accidentally paste (series/exchange tags)
            for bad in ("-EQ", "-BE", ".NS", ".BO"):
                if sym.endswith(bad): sym = sym[: -len(bad)]
            if not sym or sym in ("SYMBOL", "NSE SYMBOL"): continue
            syms.append(sym)
            names_.append(parts[1] if len(parts) > 1 and parts[1] else sym)
            inds_.append(parts[2] if len(parts) > 2 and parts[2] else "Custom")
        if not syms:
            return jsonify(error="Paste at least one symbol first."), 400
        u = pd.DataFrame({"Symbol": syms, "Company Name": names_, "Industry": inds_}).drop_duplicates("Symbol")
        if ind: u = u[u["Industry"] == ind]
    else:
        try:
            u = load_group(grp)
        except Exception as e:
            return jsonify(error=f"Could not load index list: {e}"), 502
        if ind: u = u[u["Industry"] == ind]
    sfx = ".NS" if ex == "NSE" else ".BO"
    names = {s + sfx: (nm, i) for s, nm, i in zip(u["Symbol"], u["Company Name"], u["Industry"])}
    key = f"scan:{ex}:{tf}:{hash(tuple(names))}"
    data = cached(key, 300, lambda: fetch(list(names), tf))
    rows = []
    for t, d in data.items():
        r = analyze(d, n)
        if not r or r["bars_ago"] > within: continue
        if want == "bull" and r["event"] != "Bullish CHoCH": continue
        if want == "bear" and r["event"] != "Bearish CHoCH": continue
        rows.append(dict(symbol=t.split(".")[0], name=names[t][0], industry=names[t][1], **r))
    rows.sort(key=lambda r: r["bars_ago"])
    return jsonify(rows=rows, scanned=len(data), total=len(names))


@app.route("/api/candles")
def candles():
    a = request.args
    sym, ex, tf = (a.get("symbol") or "").strip().upper(), a.get("exchange", "NSE"), a.get("tf", "1d")
    n = int(a.get("swing", 3))
    if not sym:
        return jsonify(error="Missing symbol."), 400
    sfx = ".NS" if ex == "NSE" else ".BO"
    ticker = sym + sfx
    key = f"cnd:{ticker}:{tf}"
    data = cached(key, 120, lambda: fetch([ticker], tf))
    d = data.get(ticker)
    if d is None or len(d) == 0:
        return jsonify(error="No price data available for this symbol/timeframe."), 404
    rows = [dict(time=int(pd.Timestamp(idx).timestamp()), open=round(float(o), 2), high=round(float(h), 2),
                 low=round(float(l), 2), close=round(float(c), 2))
            for idx, o, h, l, c in zip(d.index, d["Open"], d["High"], d["Low"], d["Close"])]
    return jsonify(candles=rows, swings=swing_points(d, n))


@app.route("/")
def home():
    return Response(PAGE, mimetype="text/html")


PAGE = r"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CHoCH Screener</title><style>
:root{--bg:#000;--panel:#0a0a0a;--card:#111;--bd:#232323;--tx:#eef0e8;--mu:#8a8f86;--ac:#ff9f1c;--up:#1fc25a;--dn:#ff4d4d}
*{box-sizing:border-box}body{margin:0;font:14px/1.4 system-ui,sans-serif;background:var(--bg);color:var(--tx);height:100vh;overflow:hidden}
.layout{display:flex;height:100vh}
.left{width:340px;min-width:280px;display:flex;flex-direction:column;border-right:1px solid var(--bd);background:var(--panel)}
.filters{padding:16px;border-bottom:1px solid var(--bd);overflow-y:auto;max-height:62vh}
.results{flex:1;padding:14px;overflow-y:auto;min-height:0}
.right{flex:1;display:flex;flex-direction:column;padding:16px;gap:12px;min-width:0}
h1{font-size:15px;margin:0 0 2px;letter-spacing:.3px}h1 span{color:var(--ac)}
.sub{color:var(--mu);margin:0 0 16px;font-size:11.5px}
.step{margin-bottom:14px;animation:fade .2s ease}
.hidden{display:none!important}
@keyframes fade{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
label{display:block;font-size:11px;color:var(--mu);margin-bottom:4px;text-transform:uppercase;letter-spacing:.4px}
select,input,textarea{width:100%;padding:9px;border-radius:6px;border:1px solid var(--bd);background:#000;color:var(--tx);font-size:13.5px;font-family:inherit}
select:focus,input:focus,textarea:focus{outline:none;border-color:var(--ac)}
textarea{resize:vertical}
.row2{display:flex;gap:8px}.row2>div{flex:1}
button.primary{padding:10px;border:0;border-radius:6px;background:var(--ac);color:#000;font-weight:700;font-size:13.5px;cursor:pointer;width:100%;margin-top:4px}
button.primary:disabled{opacity:.45;cursor:default}
.hint{font-size:11px;color:var(--mu);margin:6px 0 0;line-height:1.5}
.hint a{color:var(--ac)}
#st{color:var(--mu);font-size:12px;margin-bottom:10px}
.rescard{border:1px solid var(--bd);border-radius:8px;padding:10px 11px;margin-bottom:8px;cursor:pointer;background:var(--card);transition:border-color .15s}
.rescard:hover{border-color:#3a3a3a}
.rescard.active{border-color:var(--ac);background:#161208}
.rc-top{display:flex;justify-content:space-between;align-items:baseline}
.rc-sym{font-weight:700;font-size:13.5px}
.rc-ago{color:var(--mu);font-size:11px}
.rc-name{color:var(--mu);font-size:11.5px;margin-top:2px}
.pill{display:inline-block;font-size:11px;font-weight:700;padding:1px 6px;border-radius:4px;margin-top:5px}
.pill.bull{color:var(--up);background:#0d2216}
.pill.bear{color:var(--dn);background:#2a1010}
.emptynote{color:var(--mu);font-size:12.5px;padding:20px 4px;text-align:center}
#infoCard{border:1px solid var(--bd);border-radius:10px;padding:14px;background:var(--card);display:none}
#infoCard.show{display:block}
.info-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-top:8px}
.info-grid div{background:#000;border:1px solid var(--bd);border-radius:6px;padding:8px 10px}
.info-grid .l{font-size:10.5px;color:var(--mu);text-transform:uppercase;letter-spacing:.3px}
.info-grid .v{font-size:15px;font-weight:700;margin-top:2px}
#chartWrap{flex:1;border:1px solid var(--bd);border-radius:10px;overflow:hidden;background:#000;min-height:0;padding:10px;display:flex;flex-direction:column}
.toolbtn{padding:5px 10px;border-radius:6px;border:1px solid var(--bd);background:#111;color:var(--tx);font-size:12px;cursor:pointer}
.toolbtn:hover{border-color:var(--ac)}
#chartPlaceholder{height:100%;display:flex;align-items:center;justify-content:center;color:var(--mu);font-size:13px;text-align:center;padding:20px}
.keyw{margin-top:10px}
</style></head><body>
<div class="layout">
  <div class="left">
    <div class="filters">
      <h1>CHo<span>CH</span> Screener</h1>
      <p class="sub">Structure-break scanner for NSE stocks</p>

      <div class="step" id="s_grp">
        <label>1. Segment / Index</label>
        <select id="grpSel"><option value="" disabled selected>Select segment</option></select>
      </div>

      <div class="step hidden" id="s_ind">
        <label>2. Sector / Industry</label>
        <select id="indSel"><option value="">All industries</option></select>
        <div id="custwrap" class="hidden">
          <textarea id="custom" rows="4" placeholder="RELIANCE, TCS, INFY ...&#10;or paste Symbol,Company Name,Industry rows"></textarea>
          <input id="customInd" placeholder="Industry filter (optional, only works if you pasted 3 columns)" style="margin-top:8px">
          <p class="hint" id="pasteHint"></p>
        </div>
      </div>

      <div class="step hidden" id="s_final">
        <label>3. Timeframe</label>
        <select id="tf"><option value="15m">15 min</option><option value="1h">1 hour</option><option value="4h">4 hour</option><option value="1d" selected>Daily</option></select>
        <div class="row2" style="margin-top:10px">
          <div><label>CHoCH type</label><select id="type"><option value="both">Both</option><option value="bull">Bullish</option><option value="bear">Bearish</option></select></div>
          <div><label>Within (candles)</label><input id="within" type="number" value="3" min="0" max="50"></div>
        </div>
        <div style="margin-top:10px"><label>Swing size (candles each side)</label><input id="swing" type="number" value="3" min="2" max="10"></div>
        <div class="keyw hidden" id="keyw"><label>Access key</label><input id="key" type="password"></div>
        <button class="primary" id="go">Scan</button>
      </div>
    </div>
    <div class="results">
      <div id="st"></div>
      <div id="resList"><p class="emptynote">Results will appear here after you scan.</p></div>
    </div>
  </div>

  <div class="right">
    <div id="infoCard"></div>
    <div id="chartWrap"><div id="chartPlaceholder">Select a stock from the results list to load its chart here.</div></div>
  </div>
</div>
<script>
const $=i=>document.getElementById(i);
const H=()=>({'X-Key':$('key').value||localStorage.k||''});
let META={groups:[],industries:[],group_industries:{},custom_label:'Custom',nifty500_label:'Nifty500'};
let LAST_ROWS=[];

fetch('/api/meta').then(r=>r.json()).then(m=>{
  META=m;
  m.groups.forEach(g=>{const o=document.createElement('option');o.textContent=g;o.value=g;$('grpSel').appendChild(o)});
}).catch(()=>{$('keyw').classList.remove('hidden')});
$('key').value=localStorage.k||'';

function show(id){$(id).classList.remove('hidden')}
function hide(id){$(id).classList.add('hidden')}
function resetFrom(step){
  if(step<=1){hide('s_ind')}
  if(step<=2){hide('s_final')}
  $('resList').innerHTML='<p class="emptynote">Results will appear here after you scan.</p>';
  $('st').textContent='';
  clearChart();
}

function pasteKey(g){return 'paste:'+g}

$('grpSel').onchange=()=>{
  const g=$('grpSel').value;
  resetFrom(1);show('s_ind');
  if(g===META.custom_label||g===META.nifty500_label){
    hide_ind_select();show('custwrap');show('s_final');
    $('custom').value=localStorage.getItem(pasteKey(g))||'';
    if(g===META.nifty500_label){
      $('pasteHint').innerHTML='Open <a href="https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv" target="_blank">this link</a> in your own browser (it blocks bots, not you), open the CSV in Excel, select the Symbol, Company Name and Industry columns, copy, and paste them above. Saved automatically in this browser — you only need to do this once.';
    }else{
      $('pasteHint').textContent='Paste symbols one per line or comma-separated. Optionally add ",Company Name,Industry" per line for sector filtering.';
    }
  }else{
    show_ind_select();hide('custwrap');
    $('indSel').innerHTML='<option value="">All industries</option>';
    (META.group_industries[g]||[]).forEach(v=>{const o=document.createElement('option');o.textContent=v;o.value=v;$('indSel').appendChild(o)});
    show('s_final');
  }
};
function hide_ind_select(){$('indSel').classList.add('hidden')}
function show_ind_select(){$('indSel').classList.remove('hidden')}

$('custom').oninput=()=>{
  const g=$('grpSel').value;
  if(g===META.custom_label||g===META.nifty500_label){localStorage.setItem(pasteKey(g),$('custom').value)}
  show('s_final');
};

function clearChart(){
  $('infoCard').classList.remove('show');$('infoCard').innerHTML='';
  $('chartWrap').innerHTML='<div id="chartPlaceholder">Select a stock from the results list to load its chart here.</div>';
  document.querySelectorAll('.rescard').forEach(r=>r.classList.remove('active'));
}

$('go').onclick=async()=>{
  localStorage.k=$('key').value;
  $('go').disabled=true;$('st').textContent='Scanning… first run can take up to a minute.';
  $('resList').innerHTML='';clearChart();
  const isPaste=($('grpSel').value===META.custom_label||$('grpSel').value===META.nifty500_label);
  const q=new URLSearchParams({exchange:'NSE',group:$('grpSel').value,
    industry:isPaste?$('customInd').value:$('indSel').value,
    tf:$('tf').value,type:$('type').value,within:$('within').value,swing:$('swing').value,symbols:$('custom').value});
  try{
    const r=await fetch('/api/scan?'+q,{headers:H()});const d=await r.json();
    if(d.error){$('st').textContent=d.error;if(r.status==401)show('keyw');}
    else{
      LAST_ROWS=d.rows;
      $('st').textContent=`${d.rows.length} match(es) · scanned ${d.scanned} of ${d.total} stocks`;
      if(!d.rows.length){$('resList').innerHTML='<p class="emptynote">No CHoCH found in this selection. Try a wider "within" window or a different timeframe.</p>'}
      else{
        $('resList').innerHTML=d.rows.map((x,i)=>{
          const bull=x.event.startsWith('Bull');
          return `<div class="rescard" data-i="${i}">
            <div class="rc-top"><span class="rc-sym">${x.symbol}</span><span class="rc-ago">${x.bars_ago} candle(s) ago</span></div>
            <div class="rc-name">${x.name} · ${x.industry}</div>
            <span class="pill ${bull?'bull':'bear'}">${x.event}</span>
          </div>`;
        }).join('');
        document.querySelectorAll('.rescard').forEach(el=>el.onclick=()=>selectRow(parseInt(el.dataset.i)));
      }
    }
  }catch(e){$('st').textContent='Request failed: '+e}
  $('go').disabled=false;
};

function selectRow(i){
  const x=LAST_ROWS[i];
  document.querySelectorAll('.rescard').forEach(r=>r.classList.remove('active'));
  document.querySelector(`.rescard[data-i="${i}"]`).classList.add('active');
  const bull=x.event.startsWith('Bull');
  $('infoCard').classList.add('show');
  $('infoCard').innerHTML=`
    <div style="display:flex;justify-content:space-between;align-items:baseline">
      <div style="font-size:16px;font-weight:700">${x.symbol} <span style="color:var(--mu);font-weight:400;font-size:12.5px">${x.name}</span></div>
      <span class="pill ${bull?'bull':'bear'}" style="font-size:12px">${x.event}</span>
    </div>
    <div class="info-grid">
      <div><div class="l">Last Close</div><div class="v">${x.close}</div></div>
      <div><div class="l">Broken Level</div><div class="v">${x.level}</div></div>
      <div><div class="l">Candles Ago</div><div class="v">${x.bars_ago}</div></div>
      <div><div class="l">BOS Before (candles)</div><div class="v">${x.bos_ago}</div></div>
      <div><div class="l">Event Bar Time</div><div class="v" style="font-size:12px">${x.time}</div></div>
      <div><div class="l">Industry</div><div class="v" style="font-size:12px">${x.industry}</div></div>
    </div>
    <p class="hint">Last Close is the most recent completed candle (Yahoo data, ~15 min delayed) — not a live tick. TradingView's free widget is not licensed to show NSE data on outside websites at all (confirmed directly from TradingView's own docs), so the chart below is drawn from the same price data your scan used, with the broken level marked as a dashed line — look for price crossing that line around the Event Bar Time. Use the link under the chart if you want to inspect the same stock on TradingView.com itself.</p>`;
  loadChart(x.symbol,'NSE',$('tf').value,x.level,$('swing').value);
}

const TF_LABEL={'15m':'15 min','1h':'1 hour','4h':'4 hour','1d':'Daily'};
let CHART=null, SERIES=null, DRAWINGS=[], DRAW_MODE=false, PENDING=null;
let SHOW_SWINGS=true, SHOW_WATERMARK=true, SWING_LINES=[], RECENT_SWINGS=null;
let CUR_SYMBOL='', CUR_TF='';

function redrawOverlay(){
  const canvas=document.getElementById('ov'); if(!canvas||!CHART||!SERIES) return;
  const ctx=canvas.getContext('2d');
  ctx.clearRect(0,0,canvas.width,canvas.height);
  ctx.strokeStyle='#ff9f1c';ctx.lineWidth=1.5;
  DRAWINGS.forEach(dr=>{
    const x1=CHART.timeScale().timeToCoordinate(dr.p1.time), y1=SERIES.priceToCoordinate(dr.p1.price);
    const x2=CHART.timeScale().timeToCoordinate(dr.p2.time), y2=SERIES.priceToCoordinate(dr.p2.price);
    if(x1==null||x2==null||y1==null||y2==null) return;
    ctx.beginPath();ctx.moveTo(x1,y1);ctx.lineTo(x2,y2);ctx.stroke();
  });
}
function zoom(factor){
  if(!CHART) return;
  const ts=CHART.timeScale(); const r=ts.getVisibleLogicalRange(); if(!r) return;
  const c=(r.from+r.to)/2, half=(r.to-r.from)/2*factor;
  ts.setVisibleLogicalRange({from:c-half,to:c+half});
  redrawOverlay();
}
function applyWatermark(){
  if(!CHART) return;
  CHART.applyOptions({watermark:{visible:SHOW_WATERMARK,text:CUR_SYMBOL+'  ·  '+(TF_LABEL[CUR_TF]||CUR_TF)+'\nCHoCH Screener',
    color:'rgba(255,255,255,0.10)',fontSize:22,horzAlign:'center',vertAlign:'center'}});
}
function applySwingLines(){
  if(!SERIES) return;
  SWING_LINES.forEach(l=>{try{SERIES.removePriceLine(l)}catch(e){}});
  SWING_LINES=[];
  if(SHOW_SWINGS&&RECENT_SWINGS){
    if(RECENT_SWINGS.H) SWING_LINES.push(SERIES.createPriceLine({price:RECENT_SWINGS.H.price,color:'#ff4d4d',lineWidth:1,lineStyle:3,axisLabelVisible:true,title:'Recent Swing High'}));
    if(RECENT_SWINGS.L) SWING_LINES.push(SERIES.createPriceLine({price:RECENT_SWINGS.L.price,color:'#1fc25a',lineWidth:1,lineStyle:3,axisLabelVisible:true,title:'Recent Swing Low'}));
  }
}
function renderDrawList(){
  const box=$('drawList'); if(!box) return;
  if(!DRAWINGS.length){box.innerHTML='<span style="color:var(--mu);font-size:11.5px">No drawings yet — click "Draw line" then click two points on the chart.</span>';return}
  box.innerHTML=DRAWINGS.map((d,i)=>`<div style="display:flex;justify-content:space-between;align-items:center;padding:3px 0;font-size:12px">
    <span>Line ${i+1} — ${d.p1.price.toFixed(2)} → ${d.p2.price.toFixed(2)}</span>
    <button class="toolbtn" data-del="${i}" style="padding:1px 8px">×</button></div>`).join('');
  box.querySelectorAll('[data-del]').forEach(b=>b.onclick=()=>{
    DRAWINGS.splice(parseInt(b.dataset.del),1);redrawOverlay();renderDrawList();
  });
}

function loadChart(symbol,exchange,tf,level,swing){
  DRAWINGS=[];PENDING=null;DRAW_MODE=false;RECENT_SWINGS=null;SWING_LINES=[];
  CUR_SYMBOL=symbol;CUR_TF=tf;
  $('chartWrap').innerHTML=`
    <div style="display:flex;gap:6px;padding:0 0 8px;flex-wrap:wrap">
      <button class="toolbtn" id="zIn" title="Zoom in">+</button>
      <button class="toolbtn" id="zOut" title="Zoom out">−</button>
      <button class="toolbtn" id="zFit" title="Fit all candles">Fit</button>
      <button class="toolbtn" id="drawBtn" title="Click two points on the chart to draw a trendline">✎ Draw line</button>
      <button class="toolbtn" id="clearBtn" title="Remove drawn lines">Clear lines</button>
      <button class="toolbtn" id="setBtn" title="Chart settings" style="margin-left:auto">⚙ Settings</button>
    </div>
    <div id="setPanel" class="hidden" style="border:1px solid var(--bd);border-radius:8px;padding:10px;margin-bottom:8px;background:var(--card)">
      <label style="display:flex;align-items:center;gap:6px;font-size:12.5px;color:var(--tx);text-transform:none;margin-bottom:6px"><input type="checkbox" id="optSwings" checked> Show recent swing high/low</label>
      <label style="display:flex;align-items:center;gap:6px;font-size:12.5px;color:var(--tx);text-transform:none;margin-bottom:8px"><input type="checkbox" id="optWatermark" checked> Show watermark</label>
      <div style="font-size:11px;color:var(--mu);text-transform:uppercase;letter-spacing:.4px;margin-bottom:4px">Drawings</div>
      <div id="drawList"></div>
    </div>
    <div id="cchart" style="height:calc(100% - 62px);width:100%;position:relative"></div>
    <div style="text-align:right;padding:4px 6px"><a href="https://www.tradingview.com/chart/?symbol=NSE:${encodeURIComponent(symbol)}" target="_blank" style="color:var(--ac);font-size:11.5px;text-decoration:none">Inspect on TradingView.com ↗</a></div>`;
  const el=$('cchart');
  function fail(msg){el.innerHTML='<div style="height:100%;display:flex;align-items:center;justify-content:center;color:var(--mu);font-size:13px;padding:20px;text-align:center">'+msg+'</div>'}
  function draw(){
    try{
      if(!window.LightweightCharts||typeof LightweightCharts.createChart!=='function'){fail('Chart library failed to load. Check your internet connection and reload.');return}
      CHART=LightweightCharts.createChart(el,{
        layout:{background:{color:'#000'},textColor:'#eef0e8'},
        grid:{vertLines:{color:'#181818'},horzLines:{color:'#181818'}},
        timeScale:{timeVisible:true,borderColor:'#232323'},
        rightPriceScale:{borderColor:'#232323'},
      });
      applyWatermark();
      if(typeof CHART.addCandlestickSeries!=='function'){fail('Chart library version mismatch (addCandlestickSeries missing). Try a hard refresh (Ctrl/Cmd+Shift+R).');return}
      SERIES=CHART.addCandlestickSeries({upColor:'#1fc25a',downColor:'#ff4d4d',borderVisible:false,wickUpColor:'#1fc25a',wickDownColor:'#ff4d4d'});
      const ov=document.createElement('canvas');
      ov.id='ov';ov.style.position='absolute';ov.style.top='0';ov.style.left='0';ov.style.pointerEvents='none';
      el.appendChild(ov);
      function sizeAll(){
        try{CHART.applyOptions({width:el.clientWidth,height:el.clientHeight})}catch(e){}
        ov.width=el.clientWidth;ov.height=el.clientHeight;
        redrawOverlay();
      }
      new ResizeObserver(sizeAll).observe(el);
      sizeAll();
      CHART.timeScale().subscribeVisibleTimeRangeChange(redrawOverlay);
      ov.addEventListener('click',e=>{
        if(!DRAW_MODE) return;
        const rect=ov.getBoundingClientRect();
        const time=CHART.timeScale().coordinateToTime(e.clientX-rect.left);
        const price=SERIES.coordinateToPrice(e.clientY-rect.top);
        if(time==null||price==null) return;
        if(!PENDING){PENDING={time,price}}
        else{DRAWINGS.push({p1:PENDING,p2:{time,price}});PENDING=null;redrawOverlay();renderDrawList()}
      });
      $('zIn').onclick=()=>zoom(0.7);
      $('zOut').onclick=()=>zoom(1.4);
      $('zFit').onclick=()=>{CHART.timeScale().fitContent();redrawOverlay()};
      $('drawBtn').onclick=()=>{
        DRAW_MODE=!DRAW_MODE;PENDING=null;
        ov.style.pointerEvents=DRAW_MODE?'auto':'none';
        $('drawBtn').style.background=DRAW_MODE?'var(--ac)':'';
        $('drawBtn').style.color=DRAW_MODE?'#000':'';
      };
      $('clearBtn').onclick=()=>{DRAWINGS=[];PENDING=null;redrawOverlay();renderDrawList()};
      $('setBtn').onclick=()=>{$('setPanel').classList.toggle('hidden')};
      $('optSwings').onchange=e=>{SHOW_SWINGS=e.target.checked;applySwingLines()};
      $('optWatermark').onchange=e=>{SHOW_WATERMARK=e.target.checked;applyWatermark()};
      renderDrawList();
    }catch(e){fail('Chart failed to initialize: '+e);return}
    fetch('/api/candles?'+new URLSearchParams({symbol,exchange,tf,swing}),{headers:H()}).then(r=>r.json()).then(d=>{
      if(d.error){fail(d.error);return}
      if(!d.candles||!d.candles.length){fail('No candle data returned for this symbol/timeframe.');return}
      try{
        SERIES.setData(d.candles);
        SERIES.createPriceLine({price:level,color:'#ff9f1c',lineWidth:2,lineStyle:2,axisLabelVisible:true,title:'Broken level'});
        // Only the single most recent swing high and the single most recent swing
        // low - not the full history - to keep the chart readable.
        RECENT_SWINGS={H:null,L:null};
        if(d.swings){
          for(let i=d.swings.length-1;i>=0&&(!RECENT_SWINGS.H||!RECENT_SWINGS.L);i--){
            const s=d.swings[i];
            if(s.type==='H'&&!RECENT_SWINGS.H) RECENT_SWINGS.H=s;
            if(s.type==='L'&&!RECENT_SWINGS.L) RECENT_SWINGS.L=s;
          }
        }
        applySwingLines();
        CHART.timeScale().fitContent();
        redrawOverlay();
      }catch(e){fail('Chart failed to render: '+e)}
    }).catch(e=>fail('Data request failed: '+e));
  }
  if(window.LightweightCharts){draw();}
  else{
    const s=document.createElement('script');
    s.src='https://cdn.jsdelivr.net/npm/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js';
    s.onload=draw;
    s.onerror=()=>fail('Could not load the charting library from the CDN. Check your internet connection.');
    document.body.appendChild(s);
  }
}
</script></body></html>"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
