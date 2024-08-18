CREATE DATABASE IF NOT EXISTS `BookSense` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci */ /*!80016 DEFAULT ENCRYPTION='N' */;
USE `BookSense`;


-- Table structure for table `roles`
DROP TABLE IF EXISTS `roles`;
CREATE TABLE `roles` (
  `RoleId` INT NOT NULL AUTO_INCREMENT,
  `RoleName` VARCHAR(50) NOT NULL,
  `Description` VARCHAR(100) NOT NULL,
  `IsActive` TINYINT DEFAULT '1',
  PRIMARY KEY (`RoleId`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Insert example roles
INSERT INTO `roles` (RoleId, RoleName, Description, IsActive) VALUES 
(1, 'Admin', 'Administrator with full access', 1),
(2, 'User', 'Regular user with basic access', 1),
(3, 'Guest', 'Guest with limited access', 1);

-- Table structure for table `users`
DROP TABLE IF EXISTS `users`;
CREATE TABLE `users` (
  `UserId` INT NOT NULL AUTO_INCREMENT,
  `UserName` VARCHAR(50) NOT NULL,
  `Email` VARCHAR(50) NOT NULL,
  `Password` VARCHAR(255) NOT NULL,
  `RoleId` INT NOT NULL,
  `IsActive` TINYINT DEFAULT '1',
  PRIMARY KEY (`UserId`),
  KEY `RoleId` (`RoleId`),
  CONSTRAINT `FK_Role` FOREIGN KEY (`RoleId`) REFERENCES `roles` (`RoleId`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Table structure for table `books`
DROP TABLE IF EXISTS `books`;
CREATE TABLE `books` (
  `BookId` INT NOT NULL AUTO_INCREMENT,
  `ISBN13` VARCHAR(13) NOT NULL,
  `ISBN10` VARCHAR(10) DEFAULT NULL,
  `Title` VARCHAR(255) NOT NULL,
  `Subtitle` VARCHAR(255) DEFAULT NULL,
  `Authors` VARCHAR(255) NOT NULL,
  `Categories` VARCHAR(255) DEFAULT NULL,
  `Thumbnail` VARCHAR(255) DEFAULT NULL,
  `Description` TEXT,
  `PublishedYear` YEAR DEFAULT NULL,
  `AverageRating` DECIMAL(3,2) DEFAULT NULL,
  `NumPages` INT DEFAULT NULL,
  `RatingsCount` INT DEFAULT NULL,
  PRIMARY KEY (`BookId`),
  UNIQUE KEY `ISBN13` (`ISBN13`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Table structure for table `recommendations`
DROP TABLE IF EXISTS `recommendations`;
CREATE TABLE `recommendations` (
  `RecommendationId` INT NOT NULL AUTO_INCREMENT,
  `UserId` INT NOT NULL,
  `BookId` INT NOT NULL,
  `Score` DECIMAL(5,2) NOT NULL,
  `RecommendationDate` DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`RecommendationId`),
  KEY `UserId` (`UserId`),
  KEY `BookId` (`BookId`),
  CONSTRAINT `FK_User` FOREIGN KEY (`UserId`) REFERENCES `users` (`UserId`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `FK_Book` FOREIGN KEY (`BookId`) REFERENCES `books` (`BookId`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Table structure for table `user_wishlist`
DROP TABLE IF EXISTS `user_wishlist`;
CREATE TABLE `user_wishlist` (
  `WishlistId` INT NOT NULL AUTO_INCREMENT,
  `UserId` INT NOT NULL,
  `BookId` INT NOT NULL,
  `AddedDate` DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`WishlistId`),
  KEY `UserId` (`UserId`),
  KEY `BookId` (`BookId`),
  CONSTRAINT `FK_Wishlist_User` FOREIGN KEY (`UserId`) REFERENCES `users` (`UserId`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `FK_Wishlist_Book` FOREIGN KEY (`BookId`) REFERENCES `books` (`BookId`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

