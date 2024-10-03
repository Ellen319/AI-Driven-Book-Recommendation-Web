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
  `ProfileImage` VARCHAR(255) DEFAULT NULL, 
  PRIMARY KEY (`UserId`),
  KEY `RoleId` (`RoleId`),
  CONSTRAINT `FK_Role` FOREIGN KEY (`RoleId`) REFERENCES `roles` (`RoleId`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- Table structure for table `wishlist`
DROP TABLE IF EXISTS `wishlist`;
CREATE TABLE `wishlist` (
  `WishlistId` INT NOT NULL AUTO_INCREMENT,
  `UserId` INT NOT NULL,
  `BookId` VARCHAR(255),
  `Title` VARCHAR(255),  -- To store the title of the book
  `CoverImg` VARCHAR(255),  -- To store the URL of the book's cover image
  `AddedDate` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`WishlistId`),
  KEY `UserId` (`UserId`),
  CONSTRAINT `FK_Wishlist_User` FOREIGN KEY (`UserId`) REFERENCES `users` (`UserId`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

