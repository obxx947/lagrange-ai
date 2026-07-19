-- ============================================================
-- 拉格朗日AI — Haskell 模块
-- 编译：ghc -o lagrange_check lagrange_check.hs
-- ============================================================

{-# LANGUAGE OverloadedStrings #-}

module Main where

import Network.HTTP.Simple
import qualified Data.ByteString.Char8 as B
import Data.Aeson
import Data.Aeson.Types
import Control.Exception
import System.Environment

data HealthStatus = HealthStatus
  { status :: String
  , indexBuilt :: Bool
  } deriving (Show)

instance FromJSON HealthStatus where
  parseJSON = withObject "HealthStatus" $ \o ->
    HealthStatus <$> o .: "status"
                 <*> o .: "index_built"

-- | 健康检查
checkHealth :: String -> IO (Either String HealthStatus)
checkHealth baseUrl = do
  let url = baseUrl ++ "/health"
  result <- try (httpJSON $ parseRequest_ url) :: IO (Either SomeException (Response HealthStatus))
  case result of
    Right resp -> return $ Right (getResponseBody resp)
    Left ex -> return $ Left (show ex)

-- | 舰船数量
getShipCount :: String -> IO (Either String Int)
getShipCount baseUrl = do
  let url = baseUrl ++ "/api/ships"
  result <- try (httpLBS $ parseRequest_ url) :: IO (Either SomeException (Response B.ByteString))
  case result of
    Right resp -> do
      let body = getResponseBody resp
      case decode body of
        Just obj -> case parse (withObject "ships" (\o -> o .: "count")) obj of
          Success count -> return $ Right count
          Error e -> return $ Left e
        Nothing -> return $ Left "JSON解析失败"
    Left ex -> return $ Left (show ex)

main :: IO ()
main = do
  args <- getArgs
  let baseUrl = if null args then "http://127.0.0.1:3000" else head args

  putStrLn "========================================"
  putStrLn "  拉格朗日AI — Haskell 服务检查"
  putStrLn "========================================"
  putStrLn $ "  目标: " ++ baseUrl
  putStrLn ""

  health <- checkHealth baseUrl
  case health of
    Right hs -> do
      putStrLn $ "  ✅ 状态: " ++ status hs
      putStrLn $ "  📚 索引: " ++ show (indexBuilt hs)
    Left err -> putStrLn $ "  ❌ 错误: " ++ err

  ships <- getShipCount baseUrl
  case ships of
    Right count -> putStrLn $ "  🚀 舰船: " ++ show count ++ " 艘"
    Left _ -> return ()

  putStrLn "\n========================================"
