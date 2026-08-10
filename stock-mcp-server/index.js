#!/usr/bin/env node

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import { StockDataFetcher } from './fetcher.js';

/**
 * 股票信息查询MCP服务器
 */
class StockMCPServer {
  constructor() {
    this.server = new Server(
      {
        name: 'stock-mcp-server',
        version: '1.0.0',
      },
      {
        capabilities: {
          tools: {},
        },
      }
    );

    this.fetcher = new StockDataFetcher();

    this.setupHandlers();
    this.setupErrorHandling();
  }

  /**
   * 设置错误处理
   */
  setupErrorHandling() {
    this.server.onerror = (error) => {
      console.error('[MCP错误]', error);
    };

    process.on('SIGINT', async () => {
      await this.server.close();
      process.exit(0);
    });
  }

  /**
   * 设置工具处理器
   */
  setupHandlers() {
    // 列出可用工具
    this.server.setRequestHandler(ListToolsRequestSchema, async () => ({
      tools: [
        {
          name: 'get_stock_realtime',
          description: '获取股票实时数据',
          inputSchema: {
            type: 'object',
            properties: {
              stockCode: {
                type: 'string',
                description: '股票代码(6位数字，如: 000001, 600000)',
              },
            },
            required: ['stockCode'],
          },
        },
        {
          name: 'batch_get_stocks',
          description: '批量获取多只股票的实时数据',
          inputSchema: {
            type: 'object',
            properties: {
              stockCodes: {
                type: 'array',
                items: { type: 'string' },
                description: '股票代码数组(如: ["000001", "600000"])',
              },
            },
            required: ['stockCodes'],
          },
        },
        {
          name: 'search_stock',
          description: '搜索股票(支持股票代码或名称关键词)',
          inputSchema: {
            type: 'object',
            properties: {
              keyword: {
                type: 'string',
                description: '搜索关键词(股票代码或名称)',
              },
            },
            required: ['keyword'],
          },
        },
        {
          name: 'get_kline',
          description: '获取K线数据(日K/周K/月K/分钟线)',
          inputSchema: {
            type: 'object',
            properties: {
              stockCode: {
                type: 'string',
                description: '股票代码',
              },
              period: {
                type: 'string',
                description: '周期: 101=日K, 102=周K, 103=月K, 1=1分钟, 5=5分钟, 15=15分钟, 30=30分钟, 60=60分钟',
                default: '101',
              },
              count: {
                type: 'number',
                description: '获取数量(默认100)',
                default: 100,
              },
            },
            required: ['stockCode'],
          },
        },
        {
          name: 'get_rank_list',
          description: '获取涨跌幅排行榜',
          inputSchema: {
            type: 'object',
            properties: {
              type: {
                type: 'string',
                description: '排行类型: up=涨幅榜, down=跌幅榜',
                default: 'up',
              },
              count: {
                type: 'number',
                description: '获取数量(默认20)',
                default: 20,
              },
            },
          },
        },
        {
          name: 'get_sector_rank',
          description: '获取行业板块涨跌排行',
          inputSchema: {
            type: 'object',
            properties: {
              count: {
                type: 'number',
                description: '获取数量(默认20)',
                default: 20,
              },
            },
          },
        },
        {
          name: 'get_market_overview',
          description: '获取市场概况(上证/深证/创业板指数)',
          inputSchema: {
            type: 'object',
            properties: {},
          },
        },
        {
          name: 'get_shareholder_count',
          description: '获取股东人数数据(历史股东户数变化)',
          inputSchema: {
            type: 'object',
            properties: {
              stockCode: {
                type: 'string',
                description: '股票代码',
              },
            },
            required: ['stockCode'],
          },
        },
        {
          name: 'get_top_ten_holders',
          description: '获取十大流通股东数据',
          inputSchema: {
            type: 'object',
            properties: {
              stockCode: {
                type: 'string',
                description: '股票代码',
              },
            },
            required: ['stockCode'],
          },
        },
        {
          name: 'get_shareholder_trend',
          description: '获取股东增长趋势分析(基于近期股东户数变化)',
          inputSchema: {
            type: 'object',
            properties: {
              stockCode: {
                type: 'string',
                description: '股票代码',
              },
            },
            required: ['stockCode'],
          },
        },
        {
          name: 'get_money_flow',
          description: '获取资金流向数据(主力资金、超大单、大单、中单、小单)',
          inputSchema: {
            type: 'object',
            properties: {
              stockCode: {
                type: 'string',
                description: '股票代码',
              },
            },
            required: ['stockCode'],
          },
        },
        {
          name: 'get_finance_data',
          description: '获取财务数据(营收、净利润、ROE等核心指标)',
          inputSchema: {
            type: 'object',
            properties: {
              stockCode: {
                type: 'string',
                description: '股票代码',
              },
            },
            required: ['stockCode'],
          },
        },
        {
          name: 'get_technical_indicators',
          description: '获取技术指标(MA均线、MACD、RSI、KDJ、BOLL)',
          inputSchema: {
            type: 'object',
            properties: {
              stockCode: {
                type: 'string',
                description: '股票代码',
              },
              days: {
                type: 'number',
                description: '计算天数(默认60天)',
                default: 60,
              },
            },
            required: ['stockCode'],
          },
        },
        {
          name: 'get_shareholder_structure',
          description: '获取股东结构数据(散户占比、散户市值比、机构占比等)',
          inputSchema: {
            type: 'object',
            properties: {
              stockCode: {
                type: 'string',
                description: '股票代码',
              },
            },
            required: ['stockCode'],
          },
        },
        {
          name: 'get_top_ten_holdings',
          description: '获取按持仓市值排序的前十大股东',
          inputSchema: {
            type: 'object',
            properties: {
              stockCode: {
                type: 'string',
                description: '股票代码',
              },
            },
            required: ['stockCode'],
          },
        },
      ],
    }));

    // 处理工具调用
    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      try {
        const { name, arguments: args } = request.params;

        switch (name) {
          case 'get_stock_realtime':
            return await this.handleGetStockRealtime(args);

          case 'batch_get_stocks':
            return await this.handleBatchGetStocks(args);

          case 'search_stock':
            return await this.handleSearchStock(args);

          case 'get_kline':
            return await this.handleGetKline(args);

          case 'get_rank_list':
            return await this.handleGetRankList(args);

          case 'get_sector_rank':
            return await this.handleGetSectorRank(args);

          case 'get_market_overview':
            return await this.handleGetMarketOverview();

          case 'get_shareholder_count':
            return await this.handleGetShareholderCount(args);

          case 'get_top_ten_holders':
            return await this.handleGetTopTenHolders(args);

          case 'get_shareholder_trend':
            return await this.handleGetShareholderTrend(args);

          case 'get_money_flow':
            return await this.handleGetMoneyFlow(args);

          case 'get_finance_data':
            return await this.handleGetFinanceData(args);

          case 'get_technical_indicators':
            return await this.handleGetTechnicalIndicators(args);

          case 'get_shareholder_structure':
            return await this.handleGetShareholderStructure(args);

          case 'get_top_ten_holdings':
            return await this.handleGetTopTenHoldings(args);

          default:
            throw new Error(`未知工具: ${name}`);
        }
      } catch (error) {
        return {
          content: [
            {
              type: 'text',
              text: `错误: ${error.message}`,
            },
          ],
        };
      }
    });
  }

  /**
   * 处理获取股票实时数据
   */
  async handleGetStockRealtime(args) {
    const { stockCode } = args;
    const data = await this.fetcher.getStockData(stockCode);

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(data, null, 2),
        },
      ],
    };
  }

  /**
   * 处理批量获取股票数据
   */
  async handleBatchGetStocks(args) {
    const { stockCodes } = args;
    const dataList = await this.fetcher.batchGetStockData(stockCodes);

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(dataList, null, 2),
        },
      ],
    };
  }

  /**
   * 处理搜索股票
   */
  async handleSearchStock(args) {
    const { keyword } = args;
    const results = await this.fetcher.searchStock(keyword);

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(results, null, 2),
        },
      ],
    };
  }

  /**
   * 处理获取K线数据
   */
  async handleGetKline(args) {
    const { stockCode, period = '101', count = 100 } = args;
    const data = await this.fetcher.getKlineData(stockCode, period, count);

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(data, null, 2),
        },
      ],
    };
  }

  /**
   * 处理获取排行榜
   */
  async handleGetRankList(args) {
    const { type = 'up', count = 20 } = args;
    const data = await this.fetcher.getRankList(type, count);

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(data, null, 2),
        },
      ],
    };
  }

  /**
   * 处理获取板块排行
   */
  async handleGetSectorRank(args) {
    const { count = 20 } = args;
    const data = await this.fetcher.getSectorRank(count);

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(data, null, 2),
        },
      ],
    };
  }

  /**
   * 处理获取市场概况
   */
  async handleGetMarketOverview() {
    const data = await this.fetcher.getMarketOverview();

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(data, null, 2),
        },
      ],
    };
  }

  /**
   * 处理获取股东人数
   */
  async handleGetShareholderCount(args) {
    const { stockCode } = args;
    const data = await this.fetcher.getShareholderCount(stockCode);

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(data, null, 2),
        },
      ],
    };
  }

  /**
   * 处理获取十大股东
   */
  async handleGetTopTenHolders(args) {
    const { stockCode } = args;
    const data = await this.fetcher.getTopTenHolders(stockCode);

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(data, null, 2),
        },
      ],
    };
  }

  /**
   * 处理获取股东趋势
   */
  async handleGetShareholderTrend(args) {
    const { stockCode } = args;
    const data = await this.fetcher.getShareholderTrend(stockCode);

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(data, null, 2),
        },
      ],
    };
  }

  /**
   * 处理获取资金流向
   */
  async handleGetMoneyFlow(args) {
    const { stockCode } = args;
    const data = await this.fetcher.getMoneyFlow(stockCode);

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(data, null, 2),
        },
      ],
    };
  }

  /**
   * 处理获取财务数据
   */
  async handleGetFinanceData(args) {
    const { stockCode } = args;
    const data = await this.fetcher.getFinanceData(stockCode);

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(data, null, 2),
        },
      ],
    };
  }

  /**
   * 处理获取技术指标
   */
  async handleGetTechnicalIndicators(args) {
    const { stockCode, days = 60 } = args;
    const data = await this.fetcher.getTechnicalIndicators(stockCode, days);

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(data, null, 2),
        },
      ],
    };
  }

  /**
   * 处理获取股东结构
   */
  async handleGetShareholderStructure(args) {
    const { stockCode } = args;
    const data = await this.fetcher.getShareholderStructure(stockCode);

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(data, null, 2),
        },
      ],
    };
  }

  /**
   * 处理获取前十大股东持仓
   */
  async handleGetTopTenHoldings(args) {
    const { stockCode } = args;
    const data = await this.fetcher.getTopTenHoldings(stockCode);

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(data, null, 2),
        },
      ],
    };
  }

  /**
   * 启动服务器
   */
  async run() {
    const transport = new StdioServerTransport();
    await this.server.connect(transport);
    console.error('股票信息MCP服务器已启动');
  }
}

// 启动服务器
const server = new StockMCPServer();
server.run().catch(console.error);
