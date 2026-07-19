/** @type {import('jest').Config} */
// ============================================================
// 拉格朗日AI — Jest 测试配置
// ============================================================
module.exports = {
  testEnvironment: 'jsdom',
  roots: ['<rootDir>/static', '<rootDir>/tests'],
  testMatch: ['**/*.test.js', '**/*.spec.js'],
  moduleFileExtensions: ['js', 'jsx', 'ts', 'tsx', 'json'],
  transform: {
    '^.+\\.(js|jsx)$': 'babel-jest',
    '^.+\\.(ts|tsx)$': 'ts-jest',
  },
  collectCoverageFrom: [
    'static/**/*.js',
    '!static/service_worker.js',
    '!**/node_modules/**',
  ],
  coverageThreshold: {
    global: {
      branches: 50,
      functions: 50,
      lines: 50,
      statements: 50,
    },
  },
  setupFilesAfterSetup: ['<rootDir>/tests/setup.js'],
};
