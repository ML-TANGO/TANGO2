package server

import (
	"context"
	"fmt"
	"strings"

	"github.com/go-pg/pg/v10"
	sdlmicro "gitlab.suredatalab.kr/sdlmicro/middleware"
	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"
	"google.golang.org/protobuf/proto"

	"gitlab.suredatalab.kr/beymons/facilities"
)

// FIXME: Description
func (s FacilitiesServer) SearchProduct(ctx context.Context, req *facilities.SearchProductRequest) (*facilities.SearchProductResponse, error) {
	// DB Connection
	conn := pgorm.Conn()
	defer conn.Close()
	// Transaction
	tx, err := conn.Begin()
	if err != nil {
		return nil, log.InternalError(ctx, err)
	}
	defer tx.Close()

	// 기본 쿼리
	query := productQuery(ctx, conn, true)
	query = query.WrapWith("list").Table("list")

	// 전체에서 검색
	if len(req.Search) > 0 {
		query.WhereGroup(func(q *pg.Query) (*pg.Query, error) {
			q.WhereOr(fmt.Sprintf("product_name ILIKE '%%%s%%'", req.Search))
			q.WhereOr(fmt.Sprintf("manufacture_id LIKE '%s%%'", req.Search))
			q.WhereOr(fmt.Sprintf("manufacture->>'name' ILIKE '%%%s%%'", req.Search))
			q.WhereOr(fmt.Sprintf("model_number LIKE '%s%%'", req.Search))
			return q, nil
		})
	}

	// 제조사로 필터링
	if len(req.ManufactureId) > 0 {
		query.Where("manufacture_id = ?", req.ManufactureId)
	}

	// 제조사 이름으로 검색
	if len(req.ManufactureName) > 0 {
		query.Where(fmt.Sprintf("manufacture->>'name' ILIKE '%%%s%%'", req.ManufactureName))
	}

	// 모델 번호로 검색
	if len(req.Model) > 0 {
		query.Where(fmt.Sprintf("model_number ILIKE '%s%%'", req.Model))
	}

	// 제품명으로 검색
	if len(req.Name) > 0 {
		query.Where(fmt.Sprintf("product_name ILIKE '%s%%'", req.Name))
	}

	res := &facilities.SearchProductResponse{Link: make(map[string]string)}
	if req.Limit > 0 {
		count, err := query.Count()
		if err != nil {
			return nil, pgorm.GetError(ctx, err)
		} else if count == 0 {
			return res, nil
		} else {
			res.Count = uint64(count)
		}
	}

	// 정렬
	for _, order := range req.Order {
		var column string
		switch order {
		case facilities.SearchProductRequest_manufacture_name_asc:
			column = "manufacture->>'name'"
		case facilities.SearchProductRequest_manufacture_name_desc:
			column = "manufacture->>'name' DESC"

		default:
			var ok bool
			column, ok = strings.CutSuffix(facilities.SearchProductRequest_Order_name[int32(order)], "_desc")
			if ok {
				column += " DESC"
			} else {
				column, _ = strings.CutSuffix(facilities.SearchProductRequest_Order_name[int32(order)], "_asc")
			}
		}
		query.OrderExpr(column + " NULLS LAST")
	}

	// 조회 결과 제한
	if req.Limit > 0 {
		query.Limit(int(req.Limit)).Offset(int(req.Offset))
	}

	// 조회
	if err := query.ForEach(func(tuple *facilities.Product) error {
		res.Entities = append(res.Entities, proto.Clone(tuple).(*facilities.Product))
		tuple = nil
		return nil
	}); err != nil {
		return nil, pgorm.GetError(ctx, err)
	}
	if res.Count == 0 {
		res.Count = uint64(len(res.Entities))
	}

	sdlmicro.SetPagination(ctx, req.Limit, req.Offset, res.Count, res.Link)
	return res, nil
}
