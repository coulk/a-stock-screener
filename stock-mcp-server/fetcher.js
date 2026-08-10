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
        fields: 'f57,f58,f43,f44,f45,f46,f47,f48,f49,f50,f51,f52,f60,f107,f152,f161,f162,f163,f164,f165,f168,f169,f170,f171,f177,f292',
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
      throw new Error(`获取股票 ${stockCode} K线数据失败: ${error.message}`);
    }
  }

  /**
   * 获取涨跌幅排行
   * @param {string} type - 类型(up涨幅/down跌幅)
   * @param {number} count - 数量
   * @returns {Promise<Array>} 排行榜数据
   */
  async getRankList(type = 'up', count = 20) {
    try {
      const sortField = type === 'up' ? 'f3' : 'f3';
      const sortType = type === 'up' ? '-1' : '1';
      
      const params = {
        pn: '1',
        pz: count.toString(),
        po: sortType,
        np: '1',
        ut: 'fa5fd1943c7b386f172d6893dbfba10b',
        fltt: '2',
        invt: '2',
        fid: sortField,
        fs: 'm:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23',
        fields: 'f12,f14,f2,f3,f4,f5,f6,f7,f15,f16,f17,f18'
      };

      const response = await axios.get(this.rankUrl, { params, timeout: 10000 });
      
      if (response.data && response.data.data && response.data.data.diff) {
        return response.data.data.diff.map(item => ({
          stockCode: item.f12,
          stockName: item.f14,
          currentPrice: item.f2,
          changePercent: item.f3,
          changeAmount: item.f4,
          volume: item.f5,
          turnover: item.f6,
          amplitude: item.f7,
          high: item.f15,
          low: item.f16,
          open: item.f17,
          previousClose: item.f18
        }));
      }
      
      return [];
    } catch (error) {
      throw new Error(`获取排行榜失败: ${error.message}`);
    }
  }

  /**
   * 获取行业板块排行
   * @param {number} count - 数量
   * @returns {Promise<Array>} 板块数据
   */
  async getSectorRank(count = 20) {
    try {
      const params = {
        pn: '1',
        pz: count.toString(),
        po: '1',
        np: '1',
        ut: 'fa5fd1943c7b386f172d6893dbfba10b',
        fltt: '2',
        invt: '2',
        fid: 'f3',
        fs: 'm:90+t:2',
        fields: 'f12,f14,f2,f3,f4,f8,f104,f105,f106,f107'
      };

      const response = await axios.get(this.rankUrl, { params, timeout: 10000 });
      
      if (response.data && response.data.data && response.data.data.diff) {
        return response.data.data.diff.map(item => ({
          sectorCode: item.f12,
          sectorName: item.f14,
          changePercent: item.f3,
          turnover: item.f8,
          leadingStock: item.f104,
          leadingStockPrice: item.f105
        }));
      }
      
      return [];
    } catch (error) {
      throw new Error(`获取板块排行失败: ${error.message}`);
    }
  }

  /**
   * 获取市场概况
   * @returns {Promise<Object>} 市场概况数据
   */
  async getMarketOverview() {
    try {
      // 获取上证指数
      const sh = await this.getStockData('000001', '1.');
      // 获取深证成指
      const sz = await this.getStockData('399001', '0.');
      // 获取创业板指
      const cyb = await this.getStockData('399006', '0.');
      
      return {
        shanghai: {
          name: '上证指数',
          ...sh
        },
        shenzhen: {
          name: '深证成指',
          ...sz
        },
        chinext: {
          name: '创业板指',
          ...cyb
        },
        updateTime: new Date().toISOString()
      };
    } catch (error) {
      throw new Error(`获取市场概况失败: ${error.message}`);
    }
  }

  /**
   * 获取股票数据（支持自定义市场代码）
   * @param {string} stockCode - 股票代码
   * @param {string} marketPrefix - 市场前缀
   * @returns {Promise<Object>} 股票数据
   */
  async getStockData(stockCode, marketPrefix = null) {
    try {
      const secid = marketPrefix ? `${marketPrefix}${stockCode}` : this.formatStockCode(stockCode);
      const params = {
        secid: secid,
        fields: 'f57,f58,f43,f44,f45,f46,f47,f48,f49,f50,f51,f52,f60,f107,f152,f161,f162,f163,f164,f165,f168,f169,f170,f171,f177,f292',
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
   * 获取股东人数数据
   * @param {string} stockCode - 股票代码
   * @returns {Promise<Object>} 股东人数数据
   */
  async getShareholderCount(stockCode) {
    try {
      const secucode = this.convertToSecucode(stockCode);
      
      const params = {
        reportName: 'RPT_F10_EH_HOLDERNUM',
        columns: 'ALL',
        filter: `(SECUCODE="${secucode}")`,
        pageNumber: '1',
        pageSize: '20',
        sortTypes: '-1',
        sortColumns: 'END_DATE',
        source: 'WEB',
        client: 'WEB'
      };

      const response = await axios.get(this.holderUrl, { params, timeout: 10000 });
      
      if (response.data && response.data.result && response.data.result.data) {
        const data = response.data.result.data;
        return {
          stockCode: stockCode,
          shareholderData: data.map(item => ({
            endDate: item.END_DATE,
            holderNum: item.HOLDER_NUM,
            holderNumChange: item.HOLDER_NUM_CHANGE,
            holderNumChangeRate: item.HOLDER_NUM_CHANGE_RATIO,
            avgHoldingAmount: item.AVG_MARKET_CAP,
            avgHoldingAmountChange: item.AVG_MARKET_CAP_CHANGE_RATIO,
            totalMarketCap: item.TOTAL_MARKET_CAP,
            totalAShares: item.TOTAL_A_SHARES,
            period: item.INTERVAL_CHRATE
          })),
          latestHolderNum: data[0]?.HOLDER_NUM || 0,
          latestChange: data[0]?.HOLDER_NUM_CHANGE || 0,
          latestChangeRate: data[0]?.HOLDER_NUM_CHANGE_RATIO || 0,
          updateTime: new Date().toISOString()
        };
      }
      
      return { stockCode, shareholderData: [], message: '暂无股东数据' };
    } catch (error) {
      throw new Error(`获取股票 ${stockCode} 股东数据失败: ${error.message}`);
    }
  }

  /**
   * 获取十大流通股东
   * @param {string} stockCode - 股票代码
   * @returns {Promise<Object>} 十大流通股东数据
   */
  async getTopTenHolders(stockCode) {
    try {
      const secucode = this.convertToSecucode(stockCode);
      
      const params = {
        reportName: 'RPT_F10_EH_FREEHOLDERS',
        columns: 'ALL',
        filter: `(SECUCODE="${secucode}")`,
        pageNumber: '1',
        pageSize: '10',
        sortTypes: '-1,-1',
        sortColumns: 'END_DATE,HOLDER_RANK',
        source: 'WEB',
        client: 'WEB'
      };

      const response = await axios.get(this.holderUrl, { params, timeout: 10000 });
      
      if (response.data && response.data.result && response.data.result.data) {
        const data = response.data.result.data;
        return {
          stockCode: stockCode,
          reportDate: data[0]?.END_DATE || '',
          holders: data.map(item => ({
            rank: item.HOLDER_RANK,
            holderName: item.HOLDER_NAME,
            holderType: item.HOLDER_TYPE,
            holdNum: item.HOLD_NUM,
            holdRatio: item.FREE_HOLDNUM_RATIO,
            holdChange: item.HOLD_NUM_CHANGE,
            changeRatio: item.CHANGE_RATIO
          })),
          updateTime: new Date().toISOString()
        };
      }
      
      return { stockCode, holders: [], message: '暂无十大股东数据' };
    } catch (error) {
      throw new Error(`获取股票 ${stockCode} 十大股东失败: ${error.message}`);
    }
  }

  /**
   * 获取股东增长趋势分析
   * @param {string} stockCode - 股票代码
   * @returns {Promise<Object>} 股东增长趋势
   */
  async getShareholderTrend(stockCode) {
    try {
      const data = await this.getShareholderCount(stockCode);
      
      if (data.shareholderData.length === 0) {
        return { stockCode, trend: 'unknown', message: '数据不足' };
      }

      const recent = data.shareholderData.slice(0, 4);
      const increases = recent.filter(d => d.holderNumChange > 0).length;
      const decreases = recent.filter(d => d.holderNumChange < 0).length;
      
      // 计算平均变化率
      const avgChangeRate = recent.reduce((sum, d) => sum + (d.holderNumChangeRate || 0), 0) / recent.length;
      
      let trend = 'stable';
      let trendDesc = '稳定';
      
      if (increases >= 3) {
        trend = 'increasing';
        trendDesc = '持续增长';
      } else if (decreases >= 3) {
        trend = 'decreasing';
        trendDesc = '持续下降';
      } else if (avgChangeRate > 2) {
        trend = 'rising';
        trendDesc = '上升趋势';
      } else if (avgChangeRate < -2) {
        trend = 'falling';
        trendDesc = '下降趋势';
      }

      return {
        stockCode: stockCode,
        trend: trend,
        trendDescription: trendDesc,
        avgChangeRate: avgChangeRate.toFixed(2),
        recentData: recent,
        analysis: {
          increasePeriods: increases,
          decreasePeriods: decreases,
          totalPeriods: recent.length,
          latestHolderNum: data.latestHolderNum,
          latestChange: data.latestChange,
          latestChangeRate: data.latestChangeRate
        },
        updateTime: new Date().toISOString()
      };
    } catch (error) {
      throw new Error(`获取股票 ${stockCode} 股东趋势失败: ${error.message}`);
    }
  }

  /**
   * 获取资金流向数据
   * @param {string} stockCode - 股票代码
   * @returns {Promise<Object>} 资金流向数据
   */
  async getMoneyFlow(stockCode) {
    try {
      const secid = this.formatStockCode(stockCode);
      const params = {
        lmt: 0,
        klt: 101,
        secid: secid,
        fields1: 'f1,f2,f3,f7',
        fields2: 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65',
        ut: 'fa5fd1943c7b386f172d6893dbfba10b'
      };

      const response = await axios.get(this.flowUrl, { params, timeout: 10000 });
      
      if (response.data && response.data.data) {
        const flowData = response.data.data;
        
        // 解析最新一天的资金流向
        if (flowData.klines && flowData.klines.length > 0) {
          const latest = flowData.klines[flowData.klines.length - 1].split(',');
          
          return {
            stockCode: stockCode,
            stockName: flowData.name,
            date: latest[0],
            mainNetInflow: parseFloat(latest[1]) || 0,  // 主力净流入
            mainNetInflowRate: parseFloat(latest[2]) || 0,  // 主力净流入占比
            superLargeNetInflow: parseFloat(latest[3]) || 0,  // 超大单净流入
            superLargeNetInflowRate: parseFloat(latest[4]) || 0,
            largeNetInflow: parseFloat(latest[5]) || 0,  // 大单净流入
            largeNetInflowRate: parseFloat(latest[6]) || 0,
            mediumNetInflow: parseFloat(latest[7]) || 0,  // 中单净流入
            mediumNetInflowRate: parseFloat(latest[8]) || 0,
            smallNetInflow: parseFloat(latest[9]) || 0,  // 小单净流入
            smallNetInflowRate: parseFloat(latest[10]) || 0,
            updateTime: new Date().toISOString()
          };
        }
      }
      
      return { stockCode, message: '暂无资金流向数据' };
    } catch (error) {
      throw new Error(`获取股票 ${stockCode} 资金流向失败: ${error.message}`);
    }
  }

  /**
   * 获取财务数据
   * @param {string} stockCode - 股票代码
   * @returns {Promise<Object>} 财务数据
   */
  async getFinanceData(stockCode) {
    try {
      const params = {
        reportName: 'RPT_LICO_FN_CPD',
        columns: 'ALL',
        filter: `(SECURITY_CODE="${stockCode}")`,
        pageNumber: '1',
        pageSize: '4',
        sortTypes: '-1',
        sortColumns: 'REPORT_DATE',
        source: 'WEB',
        client: 'WEB'
      };

      const response = await axios.get(this.financeUrl, { params, timeout: 10000 });
      
      if (response.data && response.data.result && response.data.result.data) {
        const data = response.data.result.data;
        
        return {
          stockCode: stockCode,
          financeData: data.map(item => ({
            reportDate: item.REPORT_DATE,
            reportType: item.REPORT_TYPE_NAME,
            revenue: item.TOTAL_OPERATE_INCOME,  // 营业总收入
            netProfit: item.PARENT_NETPROFIT,  // 净利润
            netProfitYoY: item.PARENT_NETPROFIT_YOY,  // 净利润同比增长
            roe: item.WEIGHTAVG_ROE,  // 净资产收益率
            grossMargin: item.SALES_GROSS_PROFIT_RATIO,  // 销售毛利率
            netMargin: item.SALES_NET_PROFIT_RATIO,  // 销售净利率
            eps: item.BASIC_EPS,  // 每股收益
            bps: item.BPS,  // 每股净资产
            totalAssets: item.TOTAL_ASSETS,  // 总资产
            totalLiability: item.TOTAL_LIABILITIES  // 总负债
          })),
          latestReport: data[0] ? {
            date: data[0].REPORT_DATE,
            revenue: data[0].TOTAL_OPERATE_INCOME,
            netProfit: data[0].PARENT_NETPROFIT,
            roe: data[0].WEIGHTAVG_ROE,
            eps: data[0].BASIC_EPS
          } : null,
          updateTime: new Date().toISOString()
        };
      }
      
      return { stockCode, financeData: [], message: '暂无财务数据' };
    } catch (error) {
      throw new Error(`获取股票 ${stockCode} 财务数据失败: ${error.message}`);
    }
  }

  /**
   * 获取按持仓市值排序的前十大股东
   * @param {string} stockCode - 股票代码
   * @returns {Promise<Object>} 前十大股东持仓数据
   */
  async getTopTenHoldings(stockCode) {
    try {
      const secucode = this.convertToSecucode(stockCode);
      
      const params = {
        reportName: 'RPT_F10_EH_FREEHOLDERS',
        columns: 'ALL',
        filter: `(SECUCODE="${secucode}")`,
        pageNumber: '1',
        pageSize: '50',  // 获取更多数据以确保涵盖所有股东
        sortTypes: '-1,-1',  // 按报告日期降序，再按持仓市值降序
        sortColumns: 'END_DATE,HOLDER_MARKET_CAP',
        source: 'WEB',
        client: 'WEB'
      };

      const response = await axios.get(this.holderUrl, { params, timeout: 10000 });
      
      if (response.data && response.data.result && response.data.result.data) {
        const data = response.data.result.data;
        
        // 按报告日期分组，获取最新报告期的数据并按持仓市值排序
        const latestDate = data[0]?.END_DATE;
        const latestHolders = data
          .filter(item => item.END_DATE === latestDate)
          .sort((a, b) => (b.HOLDER_MARKET_CAP || 0) - (a.HOLDER_MARKET_CAP || 0))
          .slice(0, 10);
        
        return {
          stockCode: stockCode,
          reportDate: latestDate,
          topTenHoldings: latestHolders.map((item, index) => ({
            rank: index + 1,  // 重新排序排名
            holderName: item.HOLDER_NAME,
            holdNum: item.HOLD_NUM,
            holdRatio: item.FREE_HOLDNUM_RATIO || item.HOLD_RATIO || 0,
            holdMarketCap: item.HOLDER_MARKET_CAP, // 持仓市值
            holdMarketCapRatio: item.HOLD_RATIO, // 持仓市值占总股本比例
            holdChange: item.HOLD_NUM_CHANGE,
            changeRatio: item.CHANGE_RATIO,
            holderType: item.HOLDER_TYPE,
            sharesType: item.SHARES_TYPE
          })),
          updateTime: new Date().toISOString()
        };
      }
      
      return { stockCode, topTenHoldings: [], message: '暂无前十大股东持仓数据' };
    } catch (error) {
      throw new Error(`获取股票 ${stockCode} 前十大股东持仓失败: ${error.message}`);
    }
  }

  /**
   * 获取股东结构数据(散户占比、机构占比等)
   * 注意：此功能通过股东人数+十大股东数据计算得出
   * @param {string} stockCode - 股票代码
   * @returns {Promise<Object>} 股东结构数据
   */
  async getShareholderStructure(stockCode) {
    try {
      const secucode = this.convertToSecucode(stockCode);
      
      // 并行获取股东人数和十大股东数据
      const [holderData, topHoldersResponse] = await Promise.all([
        this.getShareholderCount(stockCode),
        // 直接请求获取更多历史数据
        axios.get(this.holderUrl, {
          params: {
            reportName: 'RPT_F10_EH_FREEHOLDERS',
            columns: 'ALL',
            filter: `(SECUCODE="${secucode}")`,
            pageNumber: '1',
            pageSize: '50',  // 获取更多历史数据
            sortTypes: '-1,-1',
            sortColumns: 'END_DATE,HOLDER_RANK',
            source: 'WEB',
            client: 'WEB'
          },
          timeout: 10000
        })
      ]);
      
      if (holderData.shareholderData.length === 0) {
        return { stockCode, shareholderStructure: [], message: '暂无股东结构数据' };
      }

      // 按日期分组十大股东数据
      const topHoldersMap = new Map();
      if (topHoldersResponse.data?.result?.data) {
        topHoldersResponse.data.result.data.forEach(item => {
          const date = item.END_DATE;
          if (!topHoldersMap.has(date)) {
            topHoldersMap.set(date, []);
          }
          topHoldersMap.get(date).push({
            rank: item.HOLDER_RANK,
            holderName: item.HOLDER_NAME,
            holdRatio: item.FREE_HOLDNUM_RATIO || 0
          });
        });
      }

      // 合并数据并计算散户占比
      const structureData = holderData.shareholderData.map(item => {
        // 匹配对应日期的十大股东数据
        const holders = topHoldersMap.get(item.endDate) || [];
        const topTenRatio = holders.reduce((sum, h) => sum + (h.holdRatio || 0), 0);
        const retailRatio = Math.max(0, 100 - topTenRatio);
        
        return {
          endDate: item.endDate,
          totalHolderNum: item.holderNum,
          avgHoldingAmount: item.avgHoldingAmount,
          holderNumChange: item.holderNumChange,
          holderNumChangeRate: item.holderNumChangeRate,
          // 散户占比（基于十大股东持股比例计算）
          retailHoldingRatio: retailRatio.toFixed(2),
          // 十大股东合计持股比例
          topTenHoldingRatio: topTenRatio.toFixed(2),
          // 十大股东明细（仅最新期）
          topTenHolders: holders.length > 0 ? holders : null
        };
      });

      const latest = structureData[0] || {};
      
      return {
        stockCode: stockCode,
        shareholderStructure: structureData,
        latestData: {
          endDate: latest.endDate,
          totalHolderNum: latest.totalHolderNum,
          avgHoldingAmount: latest.avgHoldingAmount,
          retailHoldingRatio: latest.retailHoldingRatio,
          topTenHoldingRatio: latest.topTenHoldingRatio,
          holderNumChange: latest.holderNumChange,
          holderNumChangeRate: latest.holderNumChangeRate,
          topTenHolders: latest.topTenHolders
        },
        updateTime: new Date().toISOString(),
        note: '散户占比 = 100% - 十大流通股东合计持股比例'
      };
    } catch (error) {
      throw new Error(`获取股票 ${stockCode} 股东结构数据失败: ${error.message}`);
    }
  }

  /**
   * 转换股票代码为SECUCODE格式
   * @param {string} stockCode - 股票代码
   * @returns {string} SECUCODE格式(如: 000001.SZ, 600000.SH)
   */
  convertToSecucode(stockCode) {
    const code = stockCode.trim();
    // 深圳市场
    if (code.startsWith('000') || code.startsWith('002') || code.startsWith('300')) {
      return `${code}.SZ`;
    }
    // 上海市场
    if (code.startsWith('60') || code.startsWith('688')) {
      return `${code}.SH`;
    }
    // 北交所
    if (code.startsWith('8')) {
      return `${code}.BJ`;
    }
    return `${code}.SH`; // 默认上海
  }

  /**
   * 计算技术指标
   * @param {string} stockCode - 股票代码
   * @param {number} days - 天数
   * @returns {Promise<Object>} 技术指标数据
   */
  async getTechnicalIndicators(stockCode, days = 60) {
    try {
      // 获取K线数据
      const klineData = await this.getKlineData(stockCode, '101', days);
      
      if (!klineData.klines || klineData.klines.length === 0) {
        return { stockCode, message: '数据不足，无法计算技术指标' };
      }

      const closes = klineData.klines.map(k => k.close);
      const highs = klineData.klines.map(k => k.high);
      const lows = klineData.klines.map(k => k.low);
      
      // 计算MA均线
      const ma5 = this.calculateMA(closes, 5);
      const ma10 = this.calculateMA(closes, 10);
      const ma20 = this.calculateMA(closes, 20);
      const ma60 = this.calculateMA(closes, 60);
      
      // 计算MACD
      const macd = this.calculateMACD(closes);
      
      // 计算RSI
      const rsi = this.calculateRSI(closes, 14);
      
      // 计算KDJ
      const kdj = this.calculateKDJ(highs, lows, closes, 9);
      
      // 计算BOLL
      const boll = this.calculateBOLL(closes, 20);

      return {
        stockCode: stockCode,
        stockName: klineData.stockName,
        currentPrice: closes[closes.length - 1],
        indicators: {
          ma: {
            ma5: ma5[ma5.length - 1],
            ma10: ma10[ma10.length - 1],
            ma20: ma20[ma20.length - 1],
            ma60: ma60[ma60.length - 1]
          },
          macd: {
            dif: macd.dif[macd.dif.length - 1],
            dea: macd.dea[macd.dea.length - 1],
            macd: macd.macd[macd.macd.length - 1]
          },
          rsi: {
            rsi14: rsi[rsi.length - 1]
          },
          kdj: {
            k: kdj.k[kdj.k.length - 1],
            d: kdj.d[kdj.d.length - 1],
            j: kdj.j[kdj.j.length - 1]
          },
          boll: {
            upper: boll.upper[boll.upper.length - 1],
            middle: boll.middle[boll.middle.length - 1],
            lower: boll.lower[boll.lower.length - 1]
          }
        },
        updateTime: new Date().toISOString()
      };
    } catch (error) {
      throw new Error(`计算股票 ${stockCode} 技术指标失败: ${error.message}`);
    }
  }

  /**
   * 计算移动平均线MA
   * @param {Array} data - 价格数组
   * @param {number} period - 周期
   * @returns {Array} MA值数组
   */
  calculateMA(data, period) {
    const result = [];
    for (let i = 0; i < data.length; i++) {
      if (i < period - 1) {
        result.push(null);
      } else {
        const sum = data.slice(i - period + 1, i + 1).reduce((a, b) => a + b, 0);
        result.push(parseFloat((sum / period).toFixed(2)));
      }
    }
    return result;
  }

  /**
   * 计算MACD指标
   * @param {Array} closes - 收盘价数组
   * @returns {Object} MACD数据
   */
  calculateMACD(closes) {
    const ema12 = this.calculateEMA(closes, 12);
    const ema26 = this.calculateEMA(closes, 26);
    
    const dif = ema12.map((val, i) => val && ema26[i] ? parseFloat((val - ema26[i]).toFixed(2)) : null);
    const dea = this.calculateEMA(dif.filter(v => v !== null), 9);
    
    // 补齐dea数组长度
    const fullDea = new Array(dif.length - dea.length).fill(null).concat(dea);
    
    const macd = dif.map((val, i) => {
      return val && fullDea[i] ? parseFloat((2 * (val - fullDea[i])).toFixed(2)) : null;
    });

    return { dif, dea: fullDea, macd };
  }

  /**
   * 计算指数移动平均EMA
   * @param {Array} data - 数据数组
   * @param {number} period - 周期
   * @returns {Array} EMA值数组
   */
  calculateEMA(data, period) {
    const result = [];
    const multiplier = 2 / (period + 1);
    
    // 第一个EMA值用SMA
    let ema = data.slice(0, period).reduce((a, b) => a + b, 0) / period;
    result.push(parseFloat(ema.toFixed(2)));
    
    for (let i = period; i < data.length; i++) {
      ema = (data[i] - ema) * multiplier + ema;
      result.push(parseFloat(ema.toFixed(2)));
    }
    
    return result;
  }

  /**
   * 计算RSI相对强弱指标
   * @param {Array} closes - 收盘价数组
   * @param {number} period - 周期
   * @returns {Array} RSI值数组
   */
  calculateRSI(closes, period = 14) {
    const result = [];
    const gains = [];
    const losses = [];
    
    for (let i = 1; i < closes.length; i++) {
      const change = closes[i] - closes[i - 1];
      gains.push(change > 0 ? change : 0);
      losses.push(change < 0 ? -change : 0);
    }
    
    for (let i = 0; i < gains.length; i++) {
      if (i < period - 1) {
        result.push(null);
      } else {
        const avgGain = gains.slice(i - period + 1, i + 1).reduce((a, b) => a + b, 0) / period;
        const avgLoss = losses.slice(i - period + 1, i + 1).reduce((a, b) => a + b, 0) / period;
        const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
        const rsi = 100 - (100 / (1 + rs));
        result.push(parseFloat(rsi.toFixed(2)));
      }
    }
    
    return [null, ...result];
  }

  /**
   * 计算KDJ指标
   * @param {Array} highs - 最高价数组
   * @param {Array} lows - 最低价数组
   * @param {Array} closes - 收盘价数组
   * @param {number} period - 周期
   * @returns {Object} KDJ数据
   */
  calculateKDJ(highs, lows, closes, period = 9) {
    const rsv = [];
    const k = [];
    const d = [];
    const j = [];
    
    for (let i = 0; i < closes.length; i++) {
      if (i < period - 1) {
        rsv.push(null);
        k.push(50);
        d.push(50);
        j.push(50);
      } else {
        const periodHigh = Math.max(...highs.slice(i - period + 1, i + 1));
        const periodLow = Math.min(...lows.slice(i - period + 1, i + 1));
        const rsvValue = periodHigh === periodLow ? 0 : 
          ((closes[i] - periodLow) / (periodHigh - periodLow)) * 100;
        rsv.push(rsvValue);
        
        const kValue = (2 * k[i - 1] + rsvValue) / 3;
        const dValue = (2 * d[i - 1] + kValue) / 3;
        const jValue = 3 * kValue - 2 * dValue;
        
        k.push(parseFloat(kValue.toFixed(2)));
        d.push(parseFloat(dValue.toFixed(2)));
        j.push(parseFloat(jValue.toFixed(2)));
      }
    }
    
    return { k, d, j };
  }

  /**
   * 计算布林带BOLL
   * @param {Array} closes - 收盘价数组
   * @param {number} period - 周期
   * @returns {Object} BOLL数据
   */
  calculateBOLL(closes, period = 20) {
    const middle = this.calculateMA(closes, period);
    const upper = [];
    const lower = [];
    
    for (let i = 0; i < closes.length; i++) {
      if (i < period - 1) {
        upper.push(null);
        lower.push(null);
      } else {
        const slice = closes.slice(i - period + 1, i + 1);
        const mean = middle[i];
        const variance = slice.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / period;
        const std = Math.sqrt(variance);
        
        upper.push(parseFloat((mean + 2 * std).toFixed(2)));
        lower.push(parseFloat((mean - 2 * std).toFixed(2)));
      }
    }
    
    return { upper, middle, lower };
  }
}
