import axios from 'axios';

/**
 * 股票数据爬取模块
 * 从东方财富网获取股票实时数据
 */
export class StockDataFetcher {
  constructor() {
    this.baseUrl = 'https://push2.eastmoney.com/api/qt/stock/get';
    this.klineUrl = 'https://push2his.eastmoney.com/api/qt/stock/kline/get';
    this.rankUrl = 'https://push2.eastmoney.com/api/qt/clist/get';
    this.holderUrl = 'https://datacenter-web.eastmoney.com/api/data/v1/get';
    this.flowUrl = 'https://push2.eastmoney.com/api/qt/stock/fflow/kline/get';
    this.financeUrl = 'https://datacenter-web.eastmoney.com/api/data/v1/get';
  }

  /**
   * 格式化股票代码
   * @param {string} stockCode - 股票代码(如: 000001, 600000)
   * @returns {string} 格式化后的代码(如: 0.000001, 1.600000)
   */
  formatStockCode(stockCode) {
    const code = stockCode.trim();
    // 深圳A股(000, 002, 300开头)
    if (code.startsWith('000') || code.startsWith('002') || code.startsWith('300')) {
      return `0.${code}`;
    }
    // 上海A股(600, 601, 603, 605, 688开头)
    if (code.startsWith('60') || code.startsWith('688')) {
      return `1.${code}`;
    }
    // 北交所(8开头)
    if (code.startsWith('8')) {
      return `0.${code}`;
    }
    return `1.${code}`; // 默认上海
  }

  /**
   * 获取股票实时数据
   * @param {string} stockCode - 股票代码
   * @returns {Promise<Object>} 股票数据
   */
  async getStockData(stockCode) {
    try {
      const secid = this.formatStockCode(stockCode);
      const params = {
        secid: secid,
        fields: 'f57,f58,f43,f44,f45,f46,f47,f48,f49,f50,f51,f52,f60,f107,f116,f117,f152,f161,f162,f163,f164,f165,f167,f168,f169,f170,f171,f177,f292',
        ut: 'fa5fd1943c7b386f172d6893dbfba10b',
        fltt: '2',
        invt: '2'
      };

      const response = await axios.get(this.baseUrl, { params, timeout: 10000 });
      
      if (response.data && response.data.data) {
        return this.parseStockData(response.data.data, stockCode);
      }
      
      throw new Error('获取数据失败');
    } catch (error) {
      throw new Error(`获取股票 ${stockCode} 数据失败: ${error.message}`);
    }
  }

  /**
   * 解析股票数据
   * @param {Object} data - 原始数据
   * @param {string} stockCode - 股票代码
   * @returns {Object} 解析后的数据
   */
  parseStockData(data, stockCode) {
    return {
      stockCode: stockCode,
      stockName: data.f58 || '',
      currentPrice: data.f43 || 0,
      changePercent: data.f170 || 0,
      changeAmount: data.f169 || 0,
      openPrice: data.f46 || 0,
      highPrice: data.f44 || 0,
      lowPrice: data.f45 || 0,
      previousClose: data.f60 || 0,
      volume: data.f47 || 0,
      turnover: data.f48 || 0,
      amplitude: data.f50 || 0,
      turnoverRate: data.f168 || 0,
      totalMarketCap: data.f116 || 0,
      circulationMarketCap: data.f117 || 0,
      pe: data.f162 || 0,
      pb: data.f167 || 0,
      updateTime: new Date().toISOString()
    };
  }

  /**
   * 批量获取股票数据
   * @param {Array<string>} stockCodes - 股票代码数组
   * @returns {Promise<Array>} 股票数据数组
   */
  async batchGetStockData(stockCodes) {
    const results = [];
    for (const code of stockCodes) {
      try {
        const data = await this.getStockData(code);
        results.push(data);
        // 避免请求过快
        await new Promise(resolve => setTimeout(resolve, 200));
      } catch (error) {
        results.push({ stockCode: code, error: error.message });
      }
    }
    return results;
  }

  /**
   * 搜索股票(简单实现，可扩展)
   * @param {string} keyword - 关键词(股票代码或名称)
   * @returns {Promise<Object>} 搜索结果
   */
  async searchStock(keyword) {
    try {
      // 如果是6位数字，直接当作股票代码查询
      if (/^\d{6}$/.test(keyword)) {
        return await this.getStockData(keyword);
      }
      
      // 使用东方财富搜索接口
      const searchUrl = 'https://searchapi.eastmoney.com/api/suggest/get';
      const params = {
        input: keyword,
        type: '14',
        token: 'D43BF722C8E33BDC906FB84D85E326E8',
        count: '5'
      };
      
      const response = await axios.get(searchUrl, { params, timeout: 10000 });
      
      if (response.data && response.data.QuotationCodeTable && response.data.QuotationCodeTable.Data) {
        return response.data.QuotationCodeTable.Data.map(item => ({
          stockCode: item.Code,
          stockName: item.Name,
          market: item.MarketType,
          type: item.SecurityTypeName
        }));
      }
      
      return [];
    } catch (error) {
      throw new Error(`搜索股票失败: ${error.message}`);
    }
  }

  /**
   * 获取K线数据
   * @param {string} stockCode - 股票代码
   * @param {string} period - 周期(日k/周k/月k/1/5/15/30/60分钟)
   * @param {number} count - 获取数量
   * @returns {Promise<Object>} K线数据
   */
  async getKlineData(stockCode, period = '101', count = 100) {
    try {
      const secid = this.formatStockCode(stockCode);
      const params = {
        secid: secid,
        fields1: 'f1,f2,f3,f4,f5,f6',
        fields2: 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61',
        klt: period,
        fqt: '1',
        beg: '0',
        end: '20500101',
        lmt: count,
        ut: 'fa5fd1943c7b386f172d6893dbfba10b'
      };

      const response = await axios.get(this.klineUrl, { params, timeout: 10000 });
      
      if (response.data && response.data.data) {
        const data = response.data.data;
        return {
          stockCode: stockCode,
          stockName: data.name,
          klines: data.klines ? data.klines.map(k => {
            const parts = k.split(',');
            return {
              date: parts[0],
              open: parseFloat(parts[1]),
              close: parseFloat(parts[2]),
              high: parseFloat(parts[3]),
              low: parseFloat(parts[4]),
              volume: parseFloat(parts[5]),
              turnover: parseFloat(parts[6]),
              changePercent: parseFloat(parts[8])
            };
          }) : []
        };
      }
      
      throw new Error('获取K线数据失败');
    } catch (error) {
      throw new Error(`获取K线数据失败: ${error.message}`);
    }
  }
}
