// ============================================================
// 拉格朗日AI — Rollup 打包配置
// ============================================================

import resolve from '@rollup/plugin-node-resolve';
import commonjs from '@rollup/plugin-commonjs';
import babel from '@rollup/plugin-babel';
import { terser } from 'rollup-plugin-terser';
import css from 'rollup-plugin-css-only';

export default {
  input: 'src/index.js',
  output: [
    {
      file: 'dist/lagrange-ui.esm.js',
      format: 'esm',
      sourcemap: true,
    },
    {
      file: 'dist/lagrange-ui.umd.js',
      format: 'umd',
      name: 'LagrangeUI',
      sourcemap: true,
      globals: {
        react: 'React',
        'react-dom': 'ReactDOM',
      },
    },
  ],
  external: ['react', 'react-dom'],
  plugins: [
    resolve({ browser: true, extensions: ['.js', '.jsx', '.ts', '.tsx'] }),
    commonjs(),
    babel({
      babelHelpers: 'bundled',
      presets: ['@babel/preset-react'],
      extensions: ['.js', '.jsx'],
    }),
    css({ output: 'lagrange-ui.css' }),
    terser(),
  ],
};
