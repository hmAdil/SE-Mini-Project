"""Mock payment gateway behind an interface."""
import uuid


class MockGateway:
    DECLINED = {"4000000000000002"}

    def charge(self, card, amount):
        card = (card or "").replace(" ", "")
        if len(card) != 16 or not card.isdigit() or card in self.DECLINED:
            return False, None
        return True, "TXN-" + uuid.uuid4().hex[:10].upper()


gateway = MockGateway()
