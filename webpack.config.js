/* eslint-disable @typescript-eslint/no-var-requires, unicorn/prefer-module */
/**
 * Lagrange AI Tactical Analysis Tool - Webpack Build Configuration
 * Multi-environment build system with dev/prod/staging modes
 * Part of Infinite Lagrange fleet combat analysis platform
 */
const path = require('path');
const webpack = require('webpack');
const HtmlWebpackPlugin = require('html-webpack-plugin');
const MiniCssExtractPlugin = require('mini-css-extract-plugin');
const TerserPlugin = require('terser-webpack-plugin');
const CssMinimizerPlugin = require('css-minimizer-webpack-plugin');
const BundleAnalyzerPlugin = require('webpack-bundle-analyzer').BundleAnalyzerPlugin;
const CopyWebpackPlugin = require('copy-webpack-plugin');
const { CleanWebpackPlugin } = require('clean-webpack-plugin');
const CompressionPlugin = require('compression-webpack-plugin');
const WorkboxPlugin = require('workbox-webpack-plugin');
const ESLintPlugin = require('eslint-webpack-plugin');
const StylelintPlugin = require('stylelint-webpack-plugin');
const ForkTsCheckerWebpackPlugin = require('fork-ts-checker-webpack-plugin');
const Dotenv = require('dotenv-webpack');
const ReactRefreshWebpackPlugin = require('@pmmmwh/react-refresh-webpack-plugin');

const PROJECT_ROOT = path.resolve(__dirname);
const SRC_DIR = path.resolve(PROJECT_ROOT, 'src');
const DIST_DIR = path.resolve(PROJECT_ROOT, 'dist');
const PUBLIC_DIR = path.resolve(PROJECT_ROOT, 'public');
const NODE_MODULES = path.resolve(PROJECT_ROOT, 'node_modules');

const LAGRANGE_VERSION = '2.0.0';

module.exports = (env, argv) => {
  const isProduction = argv.mode === 'production';
  const isDevelopment = argv.mode === 'development';
  const isStaging = env && env.staging === true;
  const enableAnalyzer = env && env.analyze === true;

  const appConfig = {
    mode: argv.mode || 'development',
    target: 'web',
    devtool: isProduction ? 'source-map' : 'eval-cheap-module-source-map',

    entry: {
      main: path.resolve(SRC_DIR, 'index.tsx'),
      admin: path.resolve(SRC_DIR, 'admin.tsx'),
      sw: path.resolve(SRC_DIR, 'service-worker.ts'),
    },

    output: {
      path: DIST_DIR,
      filename: isProduction ? 'js/[name].[contenthash:8].js' : 'js/[name].bundle.js',
      chunkFilename: isProduction ? 'js/[name].[contenthash:8].chunk.js' : 'js/[name].chunk.js',
      publicPath: '/',
      clean: true,
      crossOriginLoading: 'anonymous',
      assetModuleFilename: 'assets/[name].[hash:8][ext]',
      hashDigestLength: 8,
      hashFunction: 'xxhash64',
    },

    resolve: {
      extensions: ['.ts', '.tsx', '.js', '.jsx', '.json', '.mjs', '.cjs', '.wasm'],
      alias: {
        '@lagrange/core': path.resolve(SRC_DIR, 'core'),
        '@lagrange/ai': path.resolve(SRC_DIR, 'ai'),
        '@lagrange/tactics': path.resolve(SRC_DIR, 'tactics'),
        '@lagrange/fleet': path.resolve(SRC_DIR, 'fleet'),
        '@lagrange/analysis': path.resolve(SRC_DIR, 'analysis'),
        '@lagrange/ui': path.resolve(SRC_DIR, 'ui'),
        '@lagrange/utils': path.resolve(SRC_DIR, 'utils'),
        '@lagrange/api': path.resolve(SRC_DIR, 'api'),
        '@lagrange/config': path.resolve(SRC_DIR, 'config'),
        '@lagrange/assets': path.resolve(SRC_DIR, 'assets'),
        '@lagrange/hooks': path.resolve(SRC_DIR, 'hooks'),
        '@lagrange/types': path.resolve(SRC_DIR, 'types'),
        '@lagrange/i18n': path.resolve(SRC_DIR, 'i18n'),
        react: path.resolve(NODE_MODULES, 'react'),
        'react-dom': path.resolve(NODE_MODULES, 'react-dom'),
      },
      symlinks: true,
      modules: [SRC_DIR, NODE_MODULES],
      fallback: {
        path: require.resolve('path-browserify'),
        crypto: require.resolve('crypto-browserify'),
        stream: require.resolve('stream-browserify'),
        buffer: require.resolve('buffer'),
        util: require.resolve('util'),
        assert: require.resolve('assert'),
        fs: false,
        net: false,
        tls: false,
        child_process: false,
      },
      mainFields: ['browser', 'module', 'main'],
      conditionNames: ['import', 'module', 'browser', 'require', 'node'],
    },

    module: {
      strictExportPresence: true,
      rules: [
        {
          test: /\.(ts|tsx|js|jsx|mjs|cjs)$/,
          exclude: /node_modules/,
          use: [
            {
              loader: 'babel-loader',
              options: {
                cacheDirectory: true,
                cacheCompression: false,
                compact: isProduction,
              },
            },
            {
              loader: 'ts-loader',
              options: {
                transpileOnly: true,
                happyPackMode: false,
                compilerOptions: { module: 'esnext', moduleResolution: 'node' },
              },
            },
          ],
        },
        {
          test: /\.module\.(c|sc|sa)ss$/,
          use: [
            isProduction ? MiniCssExtractPlugin.loader : 'style-loader',
            {
              loader: 'css-loader',
              options: {
                modules: {
                  localIdentName: isProduction
                    ? '[hash:base64:8]'
                    : '[name]__[local]--[hash:base64:5]',
                  exportLocalsConvention: 'camelCaseOnly',
                  namedExport: false,
                },
                importLoaders: 2,
                sourceMap: !isProduction,
              },
            },
            {
              loader: 'postcss-loader',
              options: { sourceMap: !isProduction },
            },
            {
              loader: 'sass-loader',
              options: { sourceMap: !isProduction },
            },
          ],
        },
        {
          test: /\.(c|sc|sa)ss$/,
          exclude: /\.module\.(c|sc|sa)ss$/,
          use: [
            isProduction ? MiniCssExtractPlugin.loader : 'style-loader',
            {
              loader: 'css-loader',
              options: {
                importLoaders: 2,
                sourceMap: !isProduction,
              },
            },
            {
              loader: 'postcss-loader',
              options: { sourceMap: !isProduction },
            },
            {
              loader: 'sass-loader',
              options: { sourceMap: !isProduction },
            },
          ],
        },
        {
          test: /\.(png|jpe?g|gif|webp|avif|svg)$/i,
          type: 'asset',
          parser: { dataUrlCondition: { maxSize: 8 * 1024 } },
          generator: {
            filename: 'images/[name].[hash:8][ext]',
          },
        },
        {
          test: /\.(woff|woff2|eot|ttf|otf)$/i,
          type: 'asset/resource',
          generator: {
            filename: 'fonts/[name].[hash:8][ext]',
          },
        },
        {
          test: /\.(gltf|glb|hdr)$/i,
          type: 'asset/resource',
          generator: {
            filename: 'models/[name].[hash:8][ext]',
          },
        },
        {
          test: /\.json$/,
          type: 'json',
          parser: { parse: JSON.parse },
        },
        {
          test: /\.(graphql|gql)$/,
          exclude: /node_modules/,
          loader: 'graphql-tag/loader',
        },
        {
          test: /\.worker\.(ts|tsx|js|jsx)$/,
          use: [
            {
              loader: 'worker-loader',
              options: {
                filename: isProduction ? 'workers/[name].[contenthash:8].js' : 'workers/[name].js',
              },
            },
            'babel-loader',
            'ts-loader',
          ],
        },
      ],
    },

    plugins: [
      new CleanWebpackPlugin({
        cleanStaleWebpackAssets: true,
        dry: false,
      }),

      new webpack.DefinePlugin({
        'process.env.NODE_ENV': JSON.stringify(argv.mode),
        LAGRANGE_VERSION: JSON.stringify(LAGRANGE_VERSION),
        LAGRANGE_ENV: JSON.stringify(isStaging ? 'staging' : isProduction ? 'production' : 'development'),
        __DEV__: JSON.stringify(isDevelopment),
        __PROD__: JSON.stringify(isProduction),
        __TEST__: 'false',
      }),

      new Dotenv({
        path: isProduction ? '.env.prod' : '.env.dev',
        safe: false,
        systemvars: true,
        defaults: '.env.example',
        expand: true,
        allowEmptyValues: false,
      }),

      new HtmlWebpackPlugin({
        template: path.resolve(PUBLIC_DIR, 'index.html'),
        filename: 'index.html',
        favicon: path.resolve(PUBLIC_DIR, 'favicon.ico'),
        inject: true,
        minify: isProduction ? {
          removeComments: true,
          collapseWhitespace: true,
          removeRedundantAttributes: true,
          useShortDoctype: true,
          removeEmptyAttributes: true,
          minifyCSS: true,
          minifyJS: true,
          minifyURLs: true,
        } : false,
        meta: {
          description: 'Lagrange AI Tactical Analysis Tool - Infinite Lagrange Fleet Combat Simulator',
          viewport: 'width=device-width, initial-scale=1, shrink-to-fit=no',
          'theme-color': '#0a0e27',
          'apple-mobile-web-app-capable': 'yes',
        },
      }),

      ...(isProduction ? [new MiniCssExtractPlugin({
        filename: 'css/[name].[contenthash:8].css',
        chunkFilename: 'css/[name].[contenthash:8].chunk.css',
        ignoreOrder: true,
      })] : []),

      new ForkTsCheckerWebpackPlugin({
        typescript: {
          configFile: path.resolve(PROJECT_ROOT, 'tsconfig.json'),
          diagnosticOptions: { semantic: true, syntactic: true },
          mode: 'write-references',
        },
        eslint: {
          files: './src/**/*.{ts,tsx,js,jsx}',
          enabled: !isProduction,
        },
        formatter: 'codeframe',
      }),

      new ESLintPlugin({
        context: SRC_DIR,
        extensions: ['ts', 'tsx', 'js', 'jsx'],
        emitError: true,
        emitWarning: true,
        failOnError: isProduction,
        failOnWarning: false,
        lintDirtyModulesOnly: isDevelopment,
        threads: true,
      }),

      new StylelintPlugin({
        context: SRC_DIR,
        extensions: ['css', 'scss'],
        emitError: true,
        emitWarning: true,
        failOnError: isProduction,
        lintDirtyModulesOnly: isDevelopment,
        threads: true,
      }),

      new CopyWebpackPlugin({
        patterns: [
          { from: path.resolve(PUBLIC_DIR, 'robots.txt'), to: 'robots.txt', noErrorOnMissing: true },
          { from: path.resolve(PUBLIC_DIR, 'sitemap.xml'), to: 'sitemap.xml', noErrorOnMissing: true },
          { from: path.resolve(PUBLIC_DIR, 'manifest.json'), to: 'manifest.json', noErrorOnMissing: true },
          { from: path.resolve(PUBLIC_DIR, 'assets'), to: 'assets', noErrorOnMissing: true },
        ],
      }),

      ...(enableAnalyzer ? [new BundleAnalyzerPlugin({
        analyzerMode: 'static',
        openAnalyzer: false,
        reportFilename: 'bundle-report.html',
        defaultSizes: 'parsed',
        generateStatsFile: true,
        statsFilename: 'bundle-stats.json',
      })] : []),

      ...(isDevelopment ? [new ReactRefreshWebpackPlugin({ overlay: { entry: 'webpack-hot-middleware' } })] : []),
      ...(isDevelopment ? [new webpack.HotModuleReplacementPlugin()] : []),

      ...(isProduction ? [new WorkboxPlugin.GenerateSW({
        clientsClaim: true,
        skipWaiting: true,
        cleanupOutdatedCaches: true,
        maximumFileSizeToCacheInBytes: 5 * 1024 * 1024,
        exclude: [/\.map$/, /asset-manifest\.json$/, /LICENSE/],
        runtimeCaching: [
          {
            urlPattern: /\/api\//,
            handler: 'NetworkFirst',
            options: { cacheName: 'api-cache', expiration: { maxEntries: 50, maxAgeSeconds: 600 } },
          },
          {
            urlPattern: /\.(?:png|jpg|jpeg|svg|gif|webp)$/,
            handler: 'CacheFirst',
            options: { cacheName: 'image-cache', expiration: { maxEntries: 200, maxAgeSeconds: 86400 * 30 } },
          },
        ],
      })] : []),

      ...(isProduction ? [
        new CompressionPlugin({
          algorithm: 'gzip',
          test: /\.(js|css|html|svg|json)$/,
          threshold: 10240,
          minRatio: 0.8,
          deleteOriginalAssets: false,
        }),
        new CompressionPlugin({
          algorithm: 'brotliCompress',
          test: /\.(js|css|html|svg|json)$/,
          threshold: 10240,
          minRatio: 0.8,
          deleteOriginalAssets: false,
          filename: '[path][base].br',
        }),
      ] : []),

      new webpack.ProvidePlugin({
        Buffer: ['buffer', 'Buffer'],
        process: 'process/browser',
      }),

      new webpack.ProgressPlugin({
        activeModules: false,
        entries: true,
        percentBy: 'entries',
      }),
    ],

    optimization: {
      minimize: isProduction,
      minimizer: [
        new TerserPlugin({
          terserOptions: {
            parse: { ecma: 2020 },
            compress: {
              ecma: 5,
              comparisons: true,
              drop_console: true,
              drop_debugger: true,
              inline: 2,
              passes: 3,
              pure_funcs: ['console.log', 'console.debug'],
            },
            mangle: { safari10: true },
            output: { ecma: 5, comments: false, ascii_only: true },
          },
          parallel: true,
          extractComments: false,
        }),
        new CssMinimizerPlugin({
          minimizerOptions: {
            preset: ['default', { discardComments: { removeAll: true } }],
          },
          parallel: true,
        }),
      ],
      splitChunks: {
        chunks: 'all',
        maxInitialRequests: 25,
        minSize: 20000,
        maxSize: 244000,
        cacheGroups: {
          defaultVendors: {
            test: /[\\/]node_modules[\\/]/,
            priority: -10,
            reuseExistingChunk: true,
            name: 'vendors',
          },
          react: {
            test: /[\\/]node_modules[\\/](react|react-dom|react-router|react-router-dom)[\\/]/,
            name: 'react-vendor',
            priority: 10,
            reuseExistingChunk: true,
          },
          lagrangeCore: {
            test: /[\\/]src[\\/](core|ai|tactics)[\\/]/,
            name: 'lagrange-core',
            priority: 5,
            reuseExistingChunk: true,
          },
          lagrangeUI: {
            test: /[\\/]src[\\/](ui|assets)[\\/]/,
            name: 'lagrange-ui',
            priority: 5,
            reuseExistingChunk: true,
          },
          styles: {
            test: /\.(css|scss)$/,
            name: 'styles',
            chunks: 'all',
            enforce: true,
            priority: 20,
          },
          common: {
            name: 'common',
            minChunks: 2,
            priority: -20,
            reuseExistingChunk: true,
          },
        },
      },
      runtimeChunk: { name: 'runtime' },
      moduleIds: isProduction ? 'deterministic' : 'named',
      chunkIds: isProduction ? 'deterministic' : 'named',
      removeEmptyChunks: true,
      mergeDuplicateChunks: true,
      providedExports: true,
      usedExports: true,
      sideEffects: true,
      concatenateModules: isProduction,
      mangleExports: isProduction ? 'deterministic' : false,
      innerGraph: true,
      realContentHash: isProduction,
    },

    performance: {
      hints: isProduction ? 'warning' : false,
      maxEntrypointSize: 512000,
      maxAssetSize: 256000,
      assetFilter: (assetFilename) => !/(\.map$)|(\.br$)|(\.gz$)/.test(assetFilename),
    },

    cache: {
      type: 'filesystem',
      version: LAGRANGE_VERSION,
      cacheDirectory: path.resolve(PROJECT_ROOT, '.webpack-cache'),
      store: 'pack',
      buildDependencies: {
        config: [__filename],
        tsconfig: [path.resolve(PROJECT_ROOT, 'tsconfig.json')],
      },
      name: `${argv.mode}-${isStaging ? 'staging' : 'default'}`,
      maxMemoryGenerations: isProduction ? 1 : Infinity,
      maxAge: isProduction ? 7 * 24 * 60 * 60 * 1000 : 24 * 60 * 60 * 1000,
    },

    devServer: {
      host: process.env.HOST || '127.0.0.1',
      port: parseInt(process.env.PORT || '4000', 10),
      hot: true,
      liveReload: true,
      compress: true,
      historyApiFallback: { disableDotRule: true },
      static: {
        directory: PUBLIC_DIR,
        publicPath: '/',
        watch: true,
      },
      client: {
        overlay: { errors: true, warnings: false },
        progress: true,
        reconnect: 5,
      },
      proxy: [
        {
          context: ['/api', '/ws'],
          target: 'http://127.0.0.1:8000',
          changeOrigin: true,
          ws: true,
          secure: false,
          logLevel: 'debug',
        },
      ],
      watchFiles: {
        paths: ['src/**/*', 'public/**/*'],
        options: { usePolling: false },
      },
      devMiddleware: {
        publicPath: '/',
        writeToDisk: false,
        stats: 'minimal',
      },
      headers: {
        'Access-Control-Allow-Origin': '*',
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
      },
      open: ['/'],
    },

    stats: {
      preset: isProduction ? 'normal' : 'errors-warnings',
      colors: true,
      modules: false,
      children: false,
      chunks: false,
      chunkModules: false,
      chunkOrigins: false,
      entrypoints: false,
      errorDetails: true,
      errorsCount: true,
      warningsCount: true,
      timings: true,
      version: true,
      hash: true,
      assets: true,
      assetsSort: '!size',
    },

    externals: {
      electron: 'commonjs electron',
    },
    externalsPresets: { node: false },

    experiments: {
      topLevelAwait: true,
      asyncWebAssembly: true,
      syncWebAssembly: false,
      css: true,
      lazyCompilation: isDevelopment,
      backCompat: true,
      outputModule: false,
    },

    snapshot: {
      managedPaths: [NODE_MODULES],
      immutablePaths: [],
      buildDependencies: { hash: true, timestamp: true },
      module: { hash: true, timestamp: isDevelopment },
      resolve: { hash: true, timestamp: isDevelopment },
      resolveBuildDependencies: { hash: true, timestamp: isDevelopment },
    },

    watchOptions: {
      aggregateTimeout: 300,
      poll: false,
      ignored: /node_modules/,
      followSymlinks: false,
    },

    recordsPath: path.resolve(PROJECT_ROOT, '.webpack-records.json'),
    recordsInputPath: path.resolve(PROJECT_ROOT, '.webpack-records.json'),
    recordsOutputPath: path.resolve(PROJECT_ROOT, '.webpack-records.json'),
  };

  return appConfig;
};
